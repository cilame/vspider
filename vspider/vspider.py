import sys
import inspect
import threading
import sqlite3
import re
from urllib import request,parse

from lxml import etree

_import_module = "__main__"

#============#
# 局部变量名 #
#============#
# 通过调用函数内部的 locals 来实现线程安全
# 变量定义不可能以数字开头，不过 locals() 里面可以定义
# 为了便于传递参数且不会有被原有被定义的临时变量调用到
# 所以这里所有的临时变量名都要前置一个数字
_locals_name_   = "0_locals_"
_cur_pool_name_ = "0_pool_name_"
_db_inserter_   = "0_db_inserter_"
_content_       = "0_content_"
_cur_node_      = "0_cur_node_"
# 用来处理默认名的消重的参数，考虑线程安全，相同的表强制 << 和 ** 收集的col名必须一样
_defualt_col_   = "0_defualt_col_"
_single_col_    = "0_single_col_"
_node_col_      = "0_node_col_"

#============#
# 公共变量名 #
#============#
_filterpool_        = "_filterpool_"
_col_xpath_toggle_  = "_col_xpath_toggle_"
_col_xpath_         = "_col_xpath_"
_node_xpath_        = "_node_xpath_"
_db_create_         = "_db_create_"
_col_types_         = "_col_types_"

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
    # 为了极简主义的追求，用了非常多的黑魔法，导致
    # 不在 __name__ == "__main__" 下的脚本里不能直接使用 x 这个魔法实例
    # 若是在非 main 脚本里面使用，请使用 vspider.X() 去产生一个新的实例
    #
    # 因为引入该库之后该库会在 "__main__" 环境里面会产生一个 x 的全局变量
    # 所以你应该避免使用 x 作为为变量的名字
    # 而较为方便的是，后续一切使用方式都只需通过 x 这个唯一实例操作即可
    #
    #     import vspider
    #
    #     def some(url):
    #         print(url)
    #
    #         # 假设每页的数据结构如下
    #         # //a[1]/b/cc
    #         # //a[1]/b/dd
    #         # //a[1]/b/eee
    #         # //a[2]/b/cc
    #         # //a[2]/b/dd
    #         # //a[2]/b/eee
    #         # //a[3]/b/cc
    #         # //a[3]/b/dd
    #         # //a[3]/b/eee
    #         # //info1
    #         # //info2
    #
    #         x @ url
    #         x * '//a'
    #         x ** './b/cc/text()'
    #         x ** './b/dd/text()'
    #
    #         # 你可以用上面的方法去收集cc,dd两列数据
    #         # 该函数库会在当前脚本路径下生成 x.db 的 sqlite 文件存储数据
    #         # 上面的脚本会配置以下结构进行数据存储（目前仅支持xpath语法）
    #         # 表名 (默认用函数名字作为表名字)
    #         # +-----+
    #         # |some |
    #         # +-----+
    #         # 列名（默认用col_x作为列名，x自增，存储类型均为string）
    #         # +-------------+
    #         # |col_0 |col_1 |
    #         # +-------------+
    #
    #         # 在函数内部你还可以定义用其他表收集别的变量，定义收集类型
    #         x("table2") @ url
    #         x * '//a'
    #         x ** ('mycol_int_','./b/eee/text()')
    #
    #         # 假如你想用一个名字为table2的表来收集eee的数据
    #         # 那么你完全不需要新开另一个函数，只需在当前上面的结构后面继续配置即可
    #         # 可以用x(table2)来修改当前配置的表名字
    #         # 然后用 * 配置节点， ** 来配置当前表的收集结构
    #         # ** 配置列的时候可以用tuple或list的第一个参数传入列名
    #         # 特别是你想让数据在存储的时候使用某种类型进行存储
    #         # 表名 (使用了自定义表名)
    #         # +-------+
    #         # |table2 |
    #         # +-------+
    #         # 列名（使用了自定义的列名，使用了int类型，默认string）
    #         # +------+
    #         # |mycol |
    #         # +------+
    #         # 列名后缀配置类型目前支持
    #         # _double_
    #         # _int_
    #         # _integer_
    #         # _str_
    #         # _string_
    #         # _date_
    #
    #         # 通过名字配置表和列的好处是，如果你在其他函数里面想要-
    #         # 将其他页面的数据传到相同的表里面就只需要配置表名即可
    #
    #         # @ 是一个简单的url的get方法
    #         # 用来进行简单的url打开收集html_content，自动传入结构分析器里面
    #         # 当然，这个url打开很粗糙，但是如果你想自己传入html_content
    #         # 你可以用 & 来实现，@和&在“相同的表”里面不能同时使用
    #         import requests
    #         req = requests.get(url)
    #
    #         x("table3") & req.content
    #         x <<          '//info1/text()'
    #         x << ('info2','//info2/text()')
    #
    #         # 当一个页面你不许要收集table型的层叠结构，并且只收集一次
    #         # 那么可以用 << 进行配置，会按照如下结构进行存储
    #         # +-------+
    #         # |table3 |
    #         # +-------+
    #         # 列名（自定义的列名，默认string类型）
    #         # +-------------+
    #         # |col_0 |info2 |
    #         # +-------------+
    #
    #     for i in range(10):
    #         url = f"http://url/s?p={i}"
    #         some(url)
    #
    #=============================================================
    '''
    def __init__(self):
        self.pool = {} # 相同名字只能唯一
    
    def __and__(self, content):
        '''
        #=============================================================
        # 重载 & 方法，作为将 html_content 传入的方法
        #
        # @ 是对应 url，用自带的库进行简单的content获取的实现
        # & 是对应 content，用已经生成的content传入分析器
        #=============================================================
        '''
        try:
            name = self._get_locals()[_cur_pool_name_]
        except:
            name = self._set_pool_by_name()

        local = self._get_locals()
        if _content_ in local:
            raise "content is already exists. a table_name only use a content in a funciton locals."

        col_xpath  = self.pool[name][_col_xpath_]
        node_xpath = self.pool[name][_node_xpath_]
        local[_db_inserter_] = DB(name,content,col_xpath,node_xpath)

    def __matmul__(self,url):
        '''
        #=============================================================
        # 对 @ 进行重载
        #
        # @ 是对应 url，用自带的库进行简单的content获取的实现
        # & 是对应 content，用已经生成的content传入
        #=============================================================
        '''
        try:
            # 使用重复代码也非我的意愿，主要是因为 self._get_locals() 这个函数使用时需要非常小心
            # 这个函数基于函数栈实现，函数层深度不正常时就会出现问题，所以不如就按照最安全的方式调用即可
            # 也许是懒得去想？
            name = self._get_locals()[_cur_pool_name_]
        except:
            name = self._set_pool_by_name()

        local = self._get_locals()
        if _content_ in local:
            raise "content is already exists. one table_name only use one content in a funciton locals."

        content = self._get(url)
        
        col_xpath  = self.pool[name][_col_xpath_]
        node_xpath = self.pool[name][_node_xpath_]
        local[_db_inserter_] = DB(name,content,col_xpath,node_xpath)

    def _get(self,url):
        '''
        #=============================================================
        # url 普通的get方法，有对query参数进行quote处理以简单解决中文问题
        #=============================================================
        '''
        def f(str):
            # 这里是对 url里面的query的参数进行quote处理的部分，处理中文输入问题
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

        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.87 Safari/537.36"}
        req = request.Request(v, headers=headers)
        content = request.urlopen(req).read()
        return content


    def __lshift__(self, col_xpath_name):
        '''
        #=============================================================
        # 对 << 进行重载
        #
        # 将其作为获取列名和 xpath 路径的存储，列名不能重复
        #=============================================================
        '''
        local = self._get_locals()
        
        try:
            name = local[_cur_pool_name_]
        except:
            raise "must be init by 'x&html_content' or 'x(name)' before use <<."

        if self.pool[name][_col_xpath_toggle_]:
            if isinstance(col_xpath_name,(tuple,list)):
                # 如果为列表或元祖则代表第一位为列名
                # 这里只考虑长度大于等于2是因为后期可能会扩展更多参数的可能
                assert len(col_xpath_name) >= 2
                col   = col_xpath_name[0]
                xpath = col_xpath_name[1]
                cobk  = lambda i:i.strip()
                if len(col_xpath_name) >= 3:
                    cobk = col_xpath_name[2]
            elif isinstance(col_xpath_name,str):
                # 如果输入为字符串类型表明用默认的名字
                # 多线程调用时只有使用 locals 才不会导致名字设置不安全
                if _defualt_col_ not in local:
                    local[_defualt_col_] = {}

                if name not in local[_defualt_col_]:
                    local[_defualt_col_][name] = {}
                    local[_defualt_col_][name][_single_col_] = set()
                    
                for i in range(1000):
                    temp = "col_" + str(i)
                    if temp not in local[_defualt_col_][name][_single_col_]:
                        local[_defualt_col_][name][_single_col_].add(temp)
                        break
                col   = temp
                xpath = col_xpath_name
                cobk  = lambda i:i.strip()

            if col not in self.pool[name][_col_xpath_]:
                self.pool[name][_col_xpath_][col] = (xpath,cobk)

    def __mul__(self,xpath_node):
        '''
        #=============================================================
        # 对 * 进行重载
        #
        # 将其作为 xpath_node 的生成，配合 ** 使用，可以实现多层次结构获取
        # *  是生成匹配该 xpath 的节点并非直接收集
        # ** 是生成 * 生成的每个节点进行数据收集一个node可以配置多个列进行收集
        #=============================================================
        '''
        local = self._get_locals()
        
        try:
            name = local[_cur_pool_name_]
        except:
            raise "must be init by 'x&html_content' or 'x(name)' before use <<."

        if self.pool[name][_col_xpath_toggle_]:
            assert isinstance(xpath_node,str),"if you use 'x * xpath_node', this xpath_node must be a str"
            # 如果输入为字符串类型表明用默认的名字
            # 多线程调用时只有使用 locals 才不会导致名字设置不安全
            assert xpath_node not in self.pool[name][_node_xpath_],"node cannot be repeat."
            self.pool[name][_node_xpath_][xpath_node] = {}
            local[_cur_node_] = xpath_node

    def __pow__(self,col_xpath_name):
        '''
        #=============================================================
        # 对 ** 进行重载
        #
        # 将其作为 xpath_node 节点下收集方式的记录，使用的是节点向下收集
        # 比如有
        # //a[1]/b/c
        # //a[1]/b/dd
        # //a[2]/b/c
        # //a[2]/b/dd
        # //a[3]/b/c
        # //a[3]/b/dd
        # 那么可以这样收集
        #
        # x *  "//a"
        # x ** "./b/c"
        # x ** "./b/dd"
        #
        # *  是生成匹配该 xpath 的节点并非直接收集
        # ** 是生成 * 生成的每个节点进行数据收集结构的配置
        #=============================================================
        '''
        local = self._get_locals()
        
        try:
            name = local[_cur_pool_name_]
        except:
            raise "must be init by 'x&html_content' or 'x(name)' before use <<."

        if self.pool[name][_col_xpath_toggle_]:
            node = local[_cur_node_]
            if isinstance(col_xpath_name,(tuple,list)):
                # 如果为列表或元祖则代表第一位为列名
                # 这里只考虑长度大于等于2是因为后期也许会扩展更多参数的可能
                assert len(col_xpath_name) >= 2
                col   = col_xpath_name[0]
                xpath = col_xpath_name[1]
                cobk  = lambda i:i.strip()
                if len(col_xpath_name) >= 3:
                    cobk = col_xpath_name[2]
            elif isinstance(col_xpath_name,str):
                # 如果输入为字符串类型表明用默认的名字
                # 多线程调用时只有使用 locals 才不会导致名字设置不安全
                if _defualt_col_ not in local:
                    local[_defualt_col_] = {}

                if name not in local[_defualt_col_]:
                    local[_defualt_col_][name] = {}
                    local[_defualt_col_][name][_node_col_] = {}

                if node not in local[_defualt_col_][name][_node_col_]:
                    local[_defualt_col_][name][_node_col_][node] = set()
                    
                for i in range(1000):
                    temp = "col_" + str(i)
                    if temp not in local[_defualt_col_][name][_node_col_][node]:
                        local[_defualt_col_][name][_node_col_][node].add(temp)
                        break
                col   = temp
                xpath = col_xpath_name
                cobk  = lambda i:i.strip()

            if col not in self.pool[name][_node_xpath_][node]:
                self.pool[name][_node_xpath_][node][col] = (xpath,cobk)
    

    def __call__(self,name):
        self._set_pool_by_name(name)
        return self

    def _set_pool_by_name(self,name=None):
        '''
        #=============================================================
        # 为了让选择器能够主动选择存储表
        # 如果不指定的话，会自动选择调用的方法名
        # 也有处理一些新表建立时候必要的初始化工作
        # 都用 x 这一个全局实例进行存储
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
            self.pool[name][_node_xpath_]       = {}

        # 临时变量需要根据函数体进行临时变量的闭包化，是为了多线程的准备
        func_locals = inspect.stack()[2][0]
        if _locals_name_ not in func_locals.f_locals:
            func_locals.f_locals[_locals_name_] = {}
        
        func_locals.f_locals[_locals_name_][_cur_pool_name_] = name
        return name

    def _get_locals(self):
        '''
        #=============================================================
        # 通过获取 x 实例所在的函数里面的 locals 修改以便传参数
        # 这样的好处在于可以在多线程里面使数据传输更安全
        #
        # 虽然 locals 本身是并不提倡修改的，也并非指向真正的 locals
        # 而是 locals 的一个拷贝，不过重要的是它是一个线程安全的字典
        # 所以借用了这样的一个接口
        #=============================================================
        '''
        func_locals = inspect.stack()[2][0]
        return func_locals.f_locals[_locals_name_]

    def test(self):
        # 4 test
        name = self._get_locals()[_cur_pool_name_]
        if self.pool[name][_col_xpath_toggle_]:
            self.pool[name][_col_xpath_toggle_] = False
        print(name)
        print(self.pool)

        # 临时变量 html_content 和 name 当前使用的池名字
        print(self._get_locals())

        # 共享变量 col_xpath, pool
        for i in self.pool[name][_col_xpath_].items():
            print(i)


class DB:
    def __init__(self,table_name,content,col_xpath,node_xpath,dbname="x.db"):
        self.name = dbname
        self.conn = sqlite3.connect(self.name) # 数据库接口处，默认使用 sqlite3
        self.cursor = self.conn.cursor()
        self._insert_sql = '''insert into {} values {}'''
        self._create_sql = '''create table if not exists {} ({})'''
        self._select_sql = '''select {} from {}'''

        self.table_name  = table_name
        self.content     = content
        self.col_xpath   = col_xpath
        self.node_xpath  = node_xpath

    def insert(self,values):
        if values:
            str_values = ','.join(["({})".format(','.join(map(lambda j:'"%s"' % str(j),i))) for i in values])
            sql = self._insert_sql.format(self.table_name,str_values)
            self.cursor.execute(sql)
            self.conn.commit()

    def create(self,col_types):
        assert col_types,f"db:{self.table_name} needs at least one column name"
        str_col_types = ','.join([' '.join(i) for i in col_types])
        sql = self._create_sql.format(self.table_name,str_col_types)
        print(sql)
        self.cursor.execute(sql)

    def _mk_col_types(self):
        p = []

        def _up_col_types(i):
            v = re.findall('_double_$|_int_$|_integer_$|_str_$|_string_$|_date_$',i.lower())
            c = re.findall('^_double_$|^_int_$|^_integer_$|^_str_$|^_string_$|^_date_$',i.lower())
            if c: c = c[0]
            assert not c,f"do not only use type_suffix as name, pls add col_name eg. mycol{c}"
            
            if not v:
                p.append((i,"str"))
            else:
                if v[0] == '_double_' : p.append((i[:-8],"double"))
                if v[0] == '_int_'    : p.append((i[:-5],"int"))
                if v[0] == '_integer_': p.append((i[:-9],"integer"))
                if v[0] == '_str_'    : p.append((i[:-5],"str"))
                if v[0] == '_string_' : p.append((i[:-8],"string"))
                if v[0] == '_date_'   : p.append((i[:-6],"date"))
        
        for i in self.col_xpath:
            _up_col_types(i)

        if self.node_xpath:
            for node_xpath in self.node_xpath:
                temp = list(self.node_xpath[node_xpath])
                if p:
                    print(temp,p)
                    assert temp == list(dict(p))
                    continue
                for i in temp:
                    _up_col_types(i)

        return p

    def _analysis(self):
        # TODO 添加 json 处理的接口以便进行对 ajax 的处理
        e = etree.HTML(self.content)
        p = []

        def _col_xpath():
            q = []
            for col in self.col_xpath:
                xpath,cobk = self.col_xpath[col]
                v = e.xpath(xpath)
                if v:
                    if isinstance(v,str):
                        v = v
                    else:
                        v = v[0]
                    if not v:
                        v = "NULL"
                    elif cobk:
                        v = cobk(v)
                else:
                    v = "NULL"
                q.append(v.replace('"','""'))
            if q:
                p.append(q)

        def _node_xpath():
            for node_xpath in self.node_xpath:
                for node in e.xpath(node_xpath):
                    q = []
                    for col in self.node_xpath[node_xpath]:
                        xpath,cobk = self.node_xpath[node_xpath][col]
                        v = node.xpath(xpath)
                        if v:
                            if isinstance(v,str):
                                v = v
                            else:
                                v = v[0]
                            if not v:
                                v = "NULL"
                            elif cobk:
                                v = cobk(v)
                        else:
                            v = "NULL"
                        q.append(v.replace('"','""'))
                    p.append(q)

        _col_xpath()
        _node_xpath()

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
