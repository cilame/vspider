import sys
import inspect
import threading
import sqlite3
import re
from urllib import request,parse

from lxml import etree

local = threading.local()
_import_module = "__main__"

#============#
# 局部变量名 #
#============#
# 变量定义不可能以数字开头，不过 locals() 里面可以定义
# 为了便于传递参数且不会有被原有被定义的临时变量调用到
# 所以这里所有的临时变量名都要前置一个数字
_locals_name_   = "0_locals_"
_cur_pool_name_ = "0_pool_name_"
_db_inserter_   = "0_db_inserter_"
_content_       = "0_content_"
_db_create_     = "0_db_create_"
_col_types_     = "0_col_types_"
_defualt_col_   = "0_defualt_col_"


#============#
# 公共变量名 #
#============#
_filterpool_        = "_filterpool_"
_col_xpath_toggle_  = "_col_xpath_toggle_"
_col_xpath_         = "_col_xpath_"


class X:
    '''
    #=============================================================
    # 该库的设计哲学就是极简主义，简单却不失强大
    #
    # 极少的代码量兼顾还不错的性能
    # 能用一个脚本完成的事情绝对不需要多个脚本
    # 并且还能实现性能非差且包含了存储过程、url池的过滤的功能的数据存储
    # 做到了线程安全，可以配合 vthread 库使用，性能质变
    #
    # 注意:
    # 该库本质上走接口极简路线，所以就只会考虑在主线程里面的实现
    # 为了实现单实例多线程安全，用了非常多的黑魔法，导致
    # 不在 __name__ == "__main__" 下的脚本里使用 x 这个魔法实例将发生异常
    #
    # 因为引入该库之后该库会在 "__main__" 环境里面会产生一个 x 的全局变量
    # 所以你应该避免使用 x 作为为变量的名字
    # 而较为方便的是，后续一切使用方式都只需通过 x 这个唯一实例操作即可
    #=============================================================
    '''
    def __init__(self):
        self.pool = {} # 相同名字只能唯一
    
    def __lt__(self, content):
        '''
        #=============================================================
        # 重载 < 方法，作为将 html_content 传入的方法
        # 会在此处有二次设置名字的情况
        #
        # 注意：
        # 默认以函数名字作为 table 名字，也可以直接用函数方法设置名字
        # 当函数调用时不在一个方法里面，则什么都不做
        # 一个函数域只能用一个解析一个 content （内部函数内算另一个域）
        #
        # @ 是对应 url，用自带的库进行简单的实现
        # < 是对应 content，用已经生成的content传入
        #=============================================================
        '''
        try:
            name = self._get_locals()[_cur_pool_name_]
        except:
            name = self._set_pool_by_name()

        local = self._get_locals()
        if _content_ in local:
            raise "content is already exists. a table_name only use a content in a funciton locals."

        col_xpath = self.pool[name][_col_xpath_]
        local[_db_inserter_] = DB(name,content,col_xpath)

    def __matmul__(self,url):
        '''
        #=============================================================
        # 对 @ 进行重载
        # 将其作为一个用 python 自带库获取 url content 的方式
        # 另外，这个不能与 < 同时使用
        # 使用这种方式产生的 content 会直接传入类里面
        # 一切为了更加简化的使用方式
        #
        # @ 是对应 url，用自带的库进行简单的实现
        # < 是对应 content，用已经生成的content传入
        #=============================================================
        '''
        try:
            name = self._get_locals()[_cur_pool_name_]
        except:
            name = self._set_pool_by_name()

        local = self._get_locals()
        if _content_ in local:
            raise "content is already exists. one table_name only use one content in a funciton locals."

        # @ 和 < 的区别就在这里
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.87 Safari/537.36"}

        # 这里是对 url 进行quote处理的部分，处理中文输入问题
        def f(str):
            def _f(m):
                a = m.group(1)
                b = parse.quote(m.group(2))
                if a.strip() or b.strip():
                    return a+'='+b
                else:
                    return ''
            return re.sub('^([^=]*)=([^=]*)$',_f,str)
        v = list(parse.urlsplit(url))
        v[3] = "&".join(map(f,v[3].split('&')))
        v = parse.urlunsplit(v)
        
        req = request.Request(v, headers=headers)
        content = request.urlopen(req).read()
        
        col_xpath = self.pool[name][_col_xpath_]
        local[_db_inserter_] = DB(name,content,col_xpath)

    def __lshift__(self, col_xpath_name):
        '''
        #=============================================================
        # 对 << 进行重载
        # 将其作为获取列名和 xpath 路径的存储，列名不能重复
        #=============================================================
        '''
        local = self._get_locals()
        
        try:
            name = local[_cur_pool_name_]
        except:
            raise "must be init by 'x<html_content' or 'x(name)' before use <<."

        if self.pool[name][_col_xpath_toggle_]:
            if isinstance(col_xpath_name,(tuple,list)):
                # 如果为列表或元祖则代表第一位为列名
                # 这里只考虑长度大于等于2是因为后期可能会扩展更多参数的可能
                assert len(col_xpath_name) >= 2
                col   = col_xpath_name[0]
                xpath = col_xpath_name[1]
            elif isinstance(col_xpath_name,str):
                # 如果输入为字符串类型表明用默认的名字
                # 多线程调用时只有使用 locals 才不会导致名字设置不安全
                if _defualt_col_ not in local:
                    local[_defualt_col_] = set()
                for i in range(1000):
                    temp = name + "_col_" + str(i)
                    if temp not in local[_defualt_col_]:
                        local[_defualt_col_].add(temp)
                        break
                col   = temp
                xpath = col_xpath_name

            if col not in self.pool[name][_col_xpath_]:
                self.pool[name][_col_xpath_][col] = xpath

    def __call__(self,name):
        self._set_pool_by_name(name)
        return self

    def _set_pool_by_name(self,name=None):
        '''
        #=============================================================
        # 为了让选择器能够主动选择过滤池
        # 如果不指定的话，会自动选择调用的方法名
        #=============================================================
        '''
        if not name:
            name = inspect.stack()[2][3]
        
        if name == "<module>":
            raise "x must be used in a function."
        if name not in self.pool:
            # 池需要根据名字进行唯一化
            self.pool[name] = {}
            self.pool[name][_filterpool_]       = filterpool(name)
            self.pool[name][_col_xpath_toggle_] = True
            self.pool[name][_col_xpath_]        = {}
            self.pool[name][_db_create_]        = True
            self.pool[name][_col_types_]        = None

        # 临时变量需要根据函数体进行临时变量的闭包化，是为了多线程的准备
        func_locals = inspect.stack()[2][0]
        if _locals_name_ not in func_locals.f_locals:
            func_locals.f_locals[_locals_name_] = {}
        
        func_locals.f_locals[_locals_name_][_cur_pool_name_] = name
        return name

    def _get_locals(self):
        '''
        #=============================================================
        # 通过对 locals 修改以便传参数
        # 这样的好处在于可以在多线程里面使数据传输更安全
        # 虽然 locals 本身是并不提倡修改的，也并非真正指向 locals
        # 而是 locals 的一个拷贝，但同时也是一个线程安全的实体
        # 所以借用了这样的一个接口
        #=============================================================
        '''
        func_locals = inspect.stack()[2][0]
        return func_locals.f_locals[_locals_name_]

    def show(self):
        # 4 test
        name = self._get_locals()[_cur_pool_name_]
        if self.pool[name][_col_xpath_toggle_]:
            self.pool[name][_col_xpath_toggle_] = False
        print(name)
        print(self.pool)

        # 临时变量 < html_content 和 name 当前使用的池名字
        print(self._get_locals())

        # 共享变量 < col_xpath, pool
        for i in self.pool[name][_col_xpath_].items():
            print(i)


class DB:
    def __init__(self,table_name,content,col_xpath,dbname="x.db"):
        self.name = dbname
        self.conn = sqlite3.connect(self.name) # 数据库接口处，默认使用 sqlite3
        self.cursor = self.conn.cursor()
        self._insert_sql = '''insert into {} values {}'''
        self._create_sql = '''create table if not exists {} ({})'''
        self._select_sql = '''select {} from {}'''

        self.table_name  = table_name
        self.content     = content
        self.col_xpath   = col_xpath

    def insert(self,values):
        if values:
            str_values = ','.join(["({})".format(','.join(map(lambda j:'"%s"' % str(j),i))) for i in values])
            sql = self._insert_sql.format(self.table_name,str_values)
            self.cursor.execute(sql)
            self.conn.commit()

    def create(self,col_types):
        if col_types:
            str_col_types = ','.join([' '.join(i) for i in col_types])
            sql = self._create_sql.format(self.table_name,str_col_types)
            self.cursor.execute(sql)

    def _mk_col_types(self):
        p = []
        for i in self.col_xpath:
            v = re.findall('_double$|_int$|_integer$|_str$|_string$|_date$',i.lower())
            if not v:
                p.append((i,"str"))
            else:
                if v[0] == '_double' : p.append((i[:-7],"double"))
                if v[0] == '_int'    : p.append((i[:-4],"int"))
                if v[0] == '_integer': p.append((i[:-8],"integer"))
                if v[0] == '_str'    : p.append((i[:-4],"str"))
                if v[0] == '_string' : p.append((i[:-7],"string"))
                if v[0] == '_date'   : p.append((i[:-5],"date"))
        return p

    def _analysis(self):
        # TODO 添加 json 处理的接口以便进行对 ajax 的处理
        e = etree.HTML(self.content)
        p = []
        for col in self.col_xpath:
            v = e.xpath(self.col_xpath[col])
            if v:
                if isinstance(v,str):
                    v = v.strip()
                else:
                    v = v[0].strip()
                if not v:
                    v = "NULL"
            else:
                v = "NULL"
            p.append(v)
        if p:
            return [p]
        else:
            return p

    def __del__(self):
        if x.pool[self.table_name][_col_xpath_toggle_]:
            x.pool[self.table_name][_col_xpath_toggle_] = False
        
        # 创建列名和列类型方法
        if not x.pool[self.table_name][_col_types_]: # 减少重复执行 self._mk_col_types 函数
            x.pool[self.table_name][_col_types_] = self._mk_col_types()
        col_types = x.pool[self.table_name][_col_types_]

        # 创建数据库，通过 col_types。
        if x.pool[self.table_name][_db_create_]: # 减少重复执行 self.create 函数
            try:
                self.create(col_types)
                x.pool[self.table_name][_db_create_] = False
            except Exception as e:
                print(e)
                raise "create error."

        # 插入数据库
        # 目前只能通过lxml在content查找，后续拓展ajax数据
        self.insert(self._analysis())
        
        self.conn.close()

class filterpool:
    def __init__(self, name):
        self.name = name
        self.static_pool = None


# 池选择器，全局唯一
x = X()

sys.modules[_import_module].x = x
