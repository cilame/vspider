import sys
import inspect
import threading
import sqlite3
import re
import json
import hmac
import time
import queue
from urllib import request,parse
from collections import Iterable

# 使用前最好预装 lxml 或 jsonpath
# 因为目前仅支持这两种解析方式

try:
    from jsonpath import jsonpath
    from lxml import etree
except:
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
_cur_filter_    = "0_cur_filter_"
_db_inserter_   = "0_db_inserter_"
_content_       = "0_content_"
_cur_node_      = "0_cur_node_"
# 用来处理默认名的消重的参数，考虑线程安全，相同的表强制 << 和 ** 收集的col名必须一样
_defualt_col_   = "0_defualt_col_"
_single_col_    = "0_single_col_"
_node_col_      = "0_node_col_"
# 用来处理 x.start_url 的线程安全的参数名字
_queue_lock_    = "0_queue_lock_"


#============#
# 公共变量名 #
#============#
_filterpool_        = "_filterpool_"
_col_xpath_toggle_  = "_col_xpath_toggle_"
_col_xpath_         = "_col_xpath_"
_node_xpath_        = "_node_xpath_"
_db_create_         = "_db_create_"
_col_types_         = "_col_types_"
_next_url_pool_     = "_next_url_pool_"
_domain_            = "_domain_"


#==========#
# 函数库名 #
#==========#
_db_ = "x.db"
_salt_ = b"spark1ehorse"



#========#
# 选择器 #
#========#
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
    # *目前这里由于DB类内部方法的限制，暂时不支持使用非 main 环境使用
    # *后续可能补充在非 main 脚本里面使用，能使用 vspider.X() 去产生一个新的实例实现
    # *目前不行
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
    #         # 上面的脚本会配置以下结构进行数据存储（目前支持xpath语法和jsonpath语法）
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
    #         # 可以用x(table_name)来修改当前配置的表名字
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
    #         # 其中，@ 函数每次都会向网页请求一遍数据
    #         # 如果你想直接使用上一张表 @ 或 & 所得到的 content
    #         # 你可以直接使用 x(table_name) & x 就可以实现相同的网页不用再多请求一遍了
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
            # 为了线程安全，所以考虑使用原函数 locals 空间
            name = self._get_locals()[_cur_pool_name_]
        except:
            name = self._set_pool_by_name()

        local = self._get_locals()

        # 为了实现 content 复用，可以直接 x(table_name) & x 就可以拿到上一张表获取的内容
        if type(content) == X:
            try:
                content = local[_content_]
                if content == X:
                    return 
            except:
                raise "if you wanna use pre content. pls ensure content already exist or already get by url."
        else:
            local[_content_] = content

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
            # 为了线程安全，所以考虑使用原函数 locals 空间
            name = self._get_locals()[_cur_pool_name_]
        except:
            name = self._set_pool_by_name()

        local = self._get_locals()

        try:
            filtername = local[_cur_filter_]
            if type(filtername) != X:
                filter_pool = self.pool[_filterpool_][filtername]
            else:
                filter_pool = None
        except:
            raise "get filter pool error."

        # 过滤对象的获取，没有则不使用。一般只有你主动关闭才会没有，关闭方法: x | x
        if filter_pool:
            # 调用过滤对象的方法，如果过滤池里面不存在url则返回url，否则返回空，退出函数
            url = filter_pool.get_url_by_pool(url)
            if not url:
                local[_content_] = X
                return

        try:
            content = self._get(url)
        except:
            u = url if len(url) < 60 else url[:57] + '...'
            print('err url:',u)
            local[_content_] = X
            return 

        # 将 content 存入 locals ，为了线程安全的 content 复用
        local[_content_] = content
        
        col_xpath  = self.pool[name][_col_xpath_]
        node_xpath = self.pool[name][_node_xpath_]
        local[_db_inserter_] = DB(name,content,col_xpath,node_xpath)


    def _assemble_http(self,url):
        '''
        tools function for __gt__ .
        '''
        return url if url.startswith('http') else self.pool[_domain_] + url

    def __add__(self,xpath):
        '''
        #=============================================================
        # 对 + 进行重载
        #
        # 收集一个解析方式，通过这个解析方式来获取 next url 然后传入 self._iter_url
        # 如果没有使用 x.start_url 方法的话，那么这个方法将无效
        #=============================================================
        '''
        # 通过 content 获取 next url，将 next url 放入迭代队列
        if hasattr(self,'_iter_url'):

            # 获取局部变量地址
            local = self._get_locals()

            # 为了扩展 start_url 接口使用的参数 _queue_lock_
            if _queue_lock_ not in local:
                local[_queue_lock_] = True

            try:
                content = local[_content_]
                if content == X:
                    # 关闭锁开关，一个函数只能操作 queue_lock 锁一次
                    if local[_queue_lock_]:
                        self._queue_lock.get()
                        local[_queue_lock_] = False
                    return 
            except:
                raise "if you wanna use pre content. pls ensure content already exist or already get by url."

            # 这里需要判断是否有 next url 解析过滤器，有的话解析
            # 解析出来的 urls 去重后传入 self._iter_url 即可
            if _next_url_pool_ not in self.pool:
                raise 'If you want to use the "next_url" parser, use it with the "x.start_url(<url>)" iterator'

            # 开始分析结构
            if isinstance(xpath,str):
                _xpath = xpath
                _xfunc = self._assemble_http
            elif isinstance(xpath,(list,tuple)):
                assert len(xpath) >= 2
                _xpath = xpath[0]
                _xfunc = lambda i:xpath[1](self._assemble_http(i))
            else:
                raise "xpath type must in (str,list,tuple)."

            # 开始解析结构
            if _xpath.startswith('jsonpath_'):
                v = jsonpath(json.load(content),_xpath)
            else:
                v = etree.HTML(content).xpath(_xpath)

            # 函数过滤，然后用全局池去重
            ls = list(map(_xfunc,v))
            ls = self.pool[_next_url_pool_].get_urls_by_pool(ls)
            for i in ls:
                self._iter_url.put(i)
            

            # 关闭锁开关，一个函数只能操作 queue_lock 锁一次
            if local[_queue_lock_]:
                self._queue_lock.get()
                local[_queue_lock_] = False


    def start_url(self,ls):
        '''
        #=============================================================
        # 通过生成迭代器，让迭代器不停迭代出获取到的新的页面地址
        #
        # 也就是将迭代器同解析器一体化，函数内部解析出 next url迭代出来
        # 以一种非常类似以往直接传入所有可能的url的直接迭代方式实现
        # 也算是一种功能代码压缩的方法
        #
        #     for url in x.start_url("http://url1"):
        #         crawl(url)
        #
        #=============================================================
        '''
        if not hasattr(self,'_iter_url'):
            self._iter_url = queue.Queue()
            self._queue_lock = queue.Queue()
        else:
            raise "The start_url function can only be used once."
        
        if isinstance(ls,str):
            self._iter_url.put(ls)
            u = ls
        elif isinstance(ls,(list,tuple,Iterable)):
            for idx,i in enumerate(ls):
                if idx==0:
                    u = i
                self._iter_url.put(i)
        else:
            raise "start_url type error. type must in (str,list,tuple,Iterable)."


        # 创建解析过滤池表，这个表只是为了在解析next url的时候去重用的
        # 如果解析不去重，那么其他过滤池的调用次数就可能呈几何上升
        # 这里就是就是为了不让普通过滤池调用过多的一种优化
        if _next_url_pool_ not in self.pool:
            self.pool[_next_url_pool_] = filterpool('temp_urls_')
            self.pool[_domain_] = '://'.join(parse.urlparse(u)[:2])

        self._queue_lock.put("V") # 因为不能用empty去判断，所以需要先put进一个标记
        while True:
            try:
                yield self._iter_url.get(timeout=.5)
                self._queue_lock.put("V")
            except:
                if self._queue_lock.qsize() == 1: # 这里不能用empty判断
                    raise StopIteration
                else:
                    time.sleep(1)


    def _get(self,url):
        '''
        #=============================================================
        # url 普通的get方法，有对query参数进行quote处理以简单解决中文问题
        #=============================================================
        '''
        def f(str):
            # 这里是对 url里面的 query的参数进行 quote处理的部分，处理中文输入问题
            # 如果 url的 query里面的 value带有 = 或 & ，可能引发异常
            def _f(m):
                a = m.group(1)
                b = parse.quote(parse.unquote(m.group(2)))
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
            raise "must be init by 'x&html_content' or 'x(name)' or 'x @ url' before use <<."

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
            raise "must be init by 'x&html_content' or 'x(name)' or 'x @ url' before use <<."

        if self.pool[name][_col_xpath_toggle_]:
            if isinstance(xpath_node,(list,tuple)):
                assert len(xpath_node) >= 2,"if you use 'x * <list>' or 'x * <tulpe>', you must input a callback function for node."
                xpath_node,node_func,*_ = xpath_node
            elif isinstance(xpath_node,str):
                node_func = None
            else:
                raise "node_callback_function type error. it type must be in (str,list,tuple)"

            local[_cur_node_] = (xpath_node,node_func)
            
            # 如果输入为字符串类型表明用默认的名字
            # 多线程调用时只有使用 locals 才不会导致名字设置不安全
            if (xpath_node,node_func) in self.pool[name][_node_xpath_]:
                return
            
            self.pool[name][_node_xpath_][(xpath_node,node_func)] = {}

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
            raise "must be init by 'x&html_content' or 'x(name)' or 'x @ url' before use <<."

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


    def __or__(self,filtername):
        '''
        #=============================================================
        # 对 | 进行重载
        #
        # 通过名字，添加新的过滤池对象存储在 x 实例里面
        #=============================================================
        '''
        func_locals = inspect.stack()[1][0]
        if _locals_name_ not in func_locals.f_locals:
            func_locals.f_locals[_locals_name_] = {}

        if _filterpool_ not in self.pool:
            self.pool[_filterpool_] = {}
        if filtername not in self.pool[_filterpool_]:
            self.pool[_filterpool_][filtername] = filterpool(filtername) if type(filtername) != X else X

        # 设置一个标记，使用后可以关闭当前函数使用过滤池，会关联在 @ 函数里面使用
        # 若传入的参数类型是 X 那么就会关闭过滤池的使用
        func_locals.f_locals[_locals_name_][_cur_filter_] = filtername

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

        # 一个函数只生成一个过滤池，没有提前配置的话会默认会生成一个函数名字的过滤对象
        # 这里不直接用 __or__ 是因为 inspect.stack() 的特殊性
        if _cur_filter_ not in func_locals.f_locals[_locals_name_]:
            filtername = inspect.stack()[2][3]
            if _filterpool_ not in self.pool:
                self.pool[_filterpool_] = {}
            if filtername not in self.pool[_filterpool_]:
                self.pool[_filterpool_][filtername] = filterpool(filtername)
            func_locals.f_locals[_locals_name_][_cur_filter_] = filtername

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


    def _test(self):
        print('==当前表名=========================================')
        print(self._get_locals()[_cur_pool_name_])
        # print('==临时变量=========================================')
        # print(self._get_locals()) # 临时变量中带有 html_content（复用优化），所以不宜直接打印
        print('==共享变量=========================================')
        print(self.pool)


#============#
# 数据库连接 #
#============#
class DB:
    def __init__(self,table_name,content,col_xpath,node_xpath,dbname=_db_):
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

        f = lambda i:re.sub('_double_$|_int_$|_integer_$|_str_$|_string_$|_date_$','',i)
        if self.node_xpath:
            for node_xpath in self.node_xpath:
                temp = list(self.node_xpath[node_xpath])
                if len(p):
                    print(temp,p)
                    assert temp == list(map(f,dict(p)))
                    continue
                for j in temp:
                    _up_col_types(j)

        return p

    def _analysis(self):
        # 两种分析提取数据的实现方法
        # xpath
        # jsonpath
        e = None
        j = None
        p = []

        def _deal_cobk(v,cobk):
            if v:
                if isinstance(v,str):
                    v = v
                else:
                    v = v[0]
                v = str(v)
                if not v:
                    v = "NULL"                
                elif cobk:
                    v = cobk(v)
            else:
                v = "NULL"
            return v

        # 这里是处理 << 传入的结构
        def _col_xpath():
            q = []
            for col in self.col_xpath:
                xpath,cobk = self.col_xpath[col]
                if xpath.startswith("jsonpath_"):
                    # 这里是用json加载
                    nonlocal j
                    if not j:
                        j = json.loads(self.content)
                    try:
                        v = jsonpath(j,xpath[9:])
                        assert v
                    except Exception as err:
                        print(err)
                        raise "jsonpath node loads error. pls check json ajax data."
                    v = _deal_cobk(v,cobk)
                    q.append(v.replace('"','""'))
                    
                else:
                    # 这里以lxml处理
                    nonlocal e
                    if e is None:
                        e = etree.HTML(self.content)
                    v = e.xpath(xpath)
                    v = _deal_cobk(v,cobk)
                    q.append(v.replace('"','""'))
            if q:
                p.append(q)

        # 这里是处理 * 和 ** 传入的结构
        def _node_xpath():
            for node_xpath,node_cobk in self.node_xpath:
                if node_xpath.startswith("jsonpath_"):
                    # 这里是用json加载
                    nonlocal j
                    if not j:
                        j = json.loads(self.content)
                    nd = node_xpath[9:]
                    try:
                        node = jsonpath(j,nd)
                        assert node
                    except:
                        raise "jsonpath node loads error. pls check json ajax data."
                    if node_cobk:
                        next_node = node_cobk(node)
                    else:
                        next_node = node

                    for i in next_node:
                        if type(i)==tuple:
                            _node = list(i)
                        else:
                            _node = i
                        q = []
                        for col in self.node_xpath[(node_xpath,node_cobk)]:
                            jpath,cobk = self.node_xpath[(node_xpath,node_cobk)][col]
                            v = jsonpath(_node,jpath)
                            v = _deal_cobk(v,cobk)
                            q.append(v.replace('"','""'))
                        p.append(q)
                    
                else:
                    # 这里以lxml处理
                    nonlocal e
                    if e is None:
                        e = etree.HTML(self.content)
                    for node in e.xpath(node_xpath):
                        q = []
                        for col in self.node_xpath[(node_xpath,node_cobk)]:
                            xpath,cobk = self.node_xpath[(node_xpath,node_cobk)][col]
                            v = node.xpath(xpath)
                            v = _deal_cobk(v,cobk)
                            q.append(v.replace('"','""'))
                        p.append(q)

        _col_xpath()
        _node_xpath()

        return p


    def __del__(self):
        if x.pool[self.table_name][_col_xpath_toggle_]:
            x.pool[self.table_name][_col_xpath_toggle_] = False

        try:
            # 创建列名和列类型方法
            if not x.pool[self.table_name][_col_types_]: # 减少重复执行 self._mk_col_types 函数
                x.pool[self.table_name][_col_types_] = self._mk_col_types()
            col_types = x.pool[self.table_name][_col_types_]

            # 创建数据库，通过 col_types。
            if x.pool[self.table_name][_db_create_]: # 减少重复执行 self.create 函数
                try:
                    self.create(col_types)
                    x.pool[self.table_name][_db_create_] = False
                except Exception as err:
                    print(err)
                    raise "create error."

            # 插入数据库
            # 目前有两种方法 xpath 和 jsonpath
            self.insert(self._analysis())
        finally:
            # 目前用的对象还是x，也就是脚本目前只能在main环境下面才可以执行
            self.conn.close()
            


#========#
# 过滤池 #
#========#
class filterpool:
    '''
    #=============================================================
    # 过滤池的对象，默认是函数会自动以函数名字生成一个对象
    # 可以用 x | filtername 自定义自己要用的过滤对象
    # 相同名字的过滤池，全局唯一
    # 初始化时会通过这个对象内的name从数据库中获取url持久化存储的过滤池
    #=============================================================
    '''
    def __init__(self,name):
        self.s = set()
        self.name = "_filter_" + name
        self.starttime = time.time()
        self.resettime = time.time()
        self.timelimit = 0
        
        self.create_sql = '''create table if not exists %s
                            (id integer primary key autoincrement,
                            url char(32) unique)''' % self.name
        self.select_sql = '''select url from %s order by id desc limit 0,{}''' % self.name
        self.insert_sql = '''insert into %s values (NULL,'{}')''' % self.name

        try:
            conn = sqlite3.connect(_db_)
            conn.execute(self.create_sql)
        finally:
            conn.close()

    def get_url_by_pool(self,url):
        re_url = url

        if isinstance(url,str):
            url = url.encode()

        assert isinstance(url,bytes),"url type must be in (string, bytes)."
        url = hmac.new(_salt_,url,'md5').hexdigest()
        
        if url in self.s:
            return
        else:
            v = time.time() - self.resettime
            if v >= self.timelimit:
                self.resettime = time.time()
                self.timelimit = self._update_timelimit(20)
                self._update_localset(4000) # 默认取四千数量作为内存缓冲池
            if self.insert(url):
                return re_url

    def get_urls_by_pool(self,urls):
        p = []
        for url in urls:
            v = self.get_url_by_pool(url)
            if v:
                p.append(v)
        return p

    def insert(self,u):
        sql = self.insert_sql.format(u)
        try:
            conn = sqlite3.connect(_db_)
            conn.execute(sql)
            conn.commit()
            return True
        except:
            return False
        finally:
            conn.close()

    def _update_localset(self,n):
        sql = self.select_sql.format(n)
        try:
            conn = sqlite3.connect(_db_)
            v = conn.execute(sql)
            v = v.fetchall()
            if v:
                self.s = set(list(zip(*v))[0]) # 默认使用最新的n条数据作为缓存使用
        finally:
            conn.close()
        return v

    def _update_timelimit(self,k):
        v = (time.time() - self.starttime)**.5 * k # 渐增的重新加载内存过滤池的时间间隔
        v = v if v <= 3600 else 3600
        return v













# 池选择器，全局唯一
x = X()

sys.modules[_import_module].x = x






