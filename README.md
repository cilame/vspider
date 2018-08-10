### python 爬虫文本数据收集库 vspider，信奉极简主义
 
#### 设计初衷：能一个脚本文件写完的事情绝对不要用到两个。

如果是 sqlite 级别的数据快速收集，并且你又不想穿梭在多个文件之间花太多的代码时间，又想在执行收集和入库的函数中能够清晰地看到配置结构，那么，这就是你想要的。

> * 解析配置、入库配置、函数执行一体化，意味更少的代码
> * 自带 url 过滤池，意味着更舒适的 url 传入
> * 线程安全，意味着不俗的效率
> * 极简的 next url 解析接口设置
> * 各种配置细目，可从最简单的例子向着复杂功能发散

- ##### 安装
```
C:\Users\Administrator> pip3 install vspider
```

需要预装 lxml 或 jsonpath 库，看你需要。

- ##### 一个最简单的百度爬虫，以下代码就能快速收集前十页内容中每页的每个标题名字和标题链接，自动入库

```python
import vspider

def some(url):
    print(url)
    x @ url
    x * '//*[contains(@class,"c-container")]'
    x ** 'string(./h3/a)'
    x ** 'string(./h3/a/@href)'

for i in range(10):
    url = f"https://www.baidu.com/s?wd=你好&pn={i*10}"
    some(url); some(url) # 内部自带去重功能，这里执行两遍是为测试确实可以进行 url 过滤去重
```

详细实现：以上代码会在脚本当前路径下生成 x.db 的 sqlite3 数据库文件（建议安装一个 SQLiteSpy 以便查看数据），并且以 some 为表名（默认名字为方法名字，也可以自定义，更多用法详看后续说明），以 col_0, col_1 为列名生成一张表（默认以col_x，x为数字递增，也可以自定义名字和入库类型 int double..，默认入库类型是 string），首次执行会进行解析结构的初始化、函数库和表结构的生成，初始化只会执行一次，每次执行函数都会将收集到的数据通过 xpath 语法解析后插入数据库相应的表中。支持多表插入，也支持单个函数内多表插入。以上使用的是一般的 xpath 语法，\* 为获取节点函数，\*\* 为当前节点解析的一种补充，以上语法为每个节点解析成两列。当然如果有 json 类型的数据也可以通过 jsonpath 语法来解析，详细看后面补充说明。（import vspider 后会在 __main__ 环境里生成一个 x 的实例，如果你需要在非 __main__ 环境里里使用，可以用 x = vspider.X() 来生成一个实例来实现同样的功能）

- ##### 因为做到了线程安全，配合 vthread 能极大提高性能

```python
import vspider,vthread

@vthread.pool(10)
def some(url):
    print(url)
    x("title_url") @ url
    x * '//*[contains(@class,"c-container")]' # * 用xpath语法收集节点，每个节点将会传递给下一级处理
    x ** ('title', 'string(./h3/a)')          # ** 对每个节点进行当前节点的xpath解析，传入title列
    x ** ('url',   'string(./h3/a/@href)')    # ** 同上，这里传入url列
    
    # 解析完所有节点之后，会一次性把该页面所有收集到的数据插入数据库

for i in range(10):
    url = f"https://www.baidu.com/s?wd=你好&pn={i*10}"
    some(url)
```

详细实现：x 本身就是一个实例，实例方法就是改变当前的表名（线程安全），即 x(table_name)，这里要注意的是，x 一旦修改当前表名字则就不能再使用默认名字（函数名字表名），以上实现为生成以 title_url 为表名，以 title, url 为列名的表。用线程库 vthread 开启十条线程的线程池，多线程初始化可能会稍微有一些步骤抢先式地重复，但当创建之后所有线程都不再会再初始化。其中 @ 为使用该库内自带的普通 urlopen ，里面有简单的实现一些 url.query.values 的中文 key 的问题，实际上并不强大。所以你可以使用 x & html_content 来用自己生成 content 传入表解析器，同一张表格不能同时使用 @ 和 & 。

- ##### 两种收集数据列的方式，以及单个函数多表插入配置的注意事项

```python
import vspider

def some(url):
    print(url)
    x @ url
    # 第一种收集方式是以 * 作为节点，** 作为节点下收集的内容地址的配置，一次收集能多行数据
    # 适用于 html table 类似的层叠结构数据，目前不支持动态修改 xpath 语法，请勿在用 ** 和 << 函数时动态赋值 
    x * '//*[contains(@class,"c-container")]'
    x ** ('标题','string(./h3/a)')
    x ** ('链接','string(./h3/a/@href)')

    # 第二种收集方式是以 << 直接作为收集的配置，另外说一句这里后续再继续配置 << 同样也是可以实现多列，一次只能收集一行数据
    # 适用于 html 单个页面只有一组需要收集的数据的场景，目前不支持动态修改 xpath 语法，请勿在用 ** 和 << 函数时动态赋值 
    x("some2") @ url
    x << ("test_int_",'string(//*[@id="page"]/strong/span[2])',lambda i:i.strip()[:20])
    ## 注意：使用 ** 和 << 配置解析数据的时候，如果配置是两个参数，则第一个是列名字，第二个是解析方法，如果有第三个参数，
    ## 那么第三个参数就是一个参数数量为一的函数，处理前面 xpath 或 jsonpath 解析到的数据后续处理，处理后才会入库
    ## 如果没有第三个参数，则默认方法是 lambda i:i.strip()，如果有收集前后空格的需要，则主动添加置为 None 即可

    # 数据都是默认以字符串形式进行收集的，不过如果你想用不同的方式进行存储可以通过增加自定义名字即可实现
    # 在自定义名字后缀加上类型即可实现在数据库中存储的类型改变，例如上面 some2 表中 test_int_ 。目前支持的后缀有：
    # _double_, _int_, _integer_, _str_, _string_, _date_

for i in range(10):
    url = f"https://www.baidu.com/s?wd=你好&pn={i*10}"
    some(url)
```

注意，@ 和 & 为导入函数，目的是将 content 导入到函数里面，\* 和 \*\* 和<< 这三个方法为配置函数，是生成解析方式的函数，目前为了效率会将各个表的解析方式传入魔法实例 x 当中存储，这里的配置一旦生成就不能改变（后续可能会增加动态传递的列解析方式的开关），配置仅第一次有效。其中如果 \*\* 需要先用 \* 生成节点才能插入节点，另外如果节点解析方法（\* 和 \*\*）和单页解析方法（<<）混用的话注意要列名字配置全部都相同即可，或者如果都是用的默认名字，只需要数量相同即可。

- ##### 关于 html_content 的复用，关于直接传入其他方法获取到的 html_content

```python
import vspider

def some(url):
    print(url)
    x @ url
    x * '//*[contains(@class,"c-container")]'
    x ** ('标题','string(./h3/a)')
    x ** ('链接','string(./h3/a/@href)')

    # 由于 @ 方法本身就是对 url 的一次请求，并且在不配置过滤池的前提下一个函数内用的是 _filter_+<函数名字> 
    # 作为表名字的数据库过滤池，例如当前的过滤池名字就为 _filter_some ，未改变池名字情况下，之后的 @ 都会有去重
    # 所以第二次的 @ 相同一个 url 方法就会被过滤掉，不过从正常函数编程角度来思考的话，
    # 由于本身就是对同一个 url 进行打开的操作，本身就不许要重新请求一遍，用下面的方法就可以直接使用上面获得的 content
    # 没有 content 则会报出异常
    x("some2") & x
    x << ("test_int_",'string(//*[@id="page"]/strong/span[2])',lambda i:i.strip()[:20])

    # 由于 @ 方法实现目前还比较粗糙，这里用 requests 库来示范直接用获取到的 content 传入解析器。
    # 将上面的 "some2" 表名字和表解析都注释掉，然后打开下面的注释即可测试。
    # import requests
    # content = requests.get(url).content
    # x("some2") & content
    # x << ("test_int_",'string(//*[@id="page"]/strong/span[2])',lambda i:i.strip()[:20])
    ## 注意，直接传入 content 有个弊端就是 url 无法加入过滤池，所幸的是，后续会开发传入自定义 requests 的方法
    ## 传入自定义的 requests 方法之后，就可以直接用 @ 方法实现传入参数等... 后续的接口在实现之后会再补充说明

for i in range(10):
    url = f"https://www.baidu.com/s?wd=你好&pn={i*10}"
    some(url)
```

- ##### 关于 url 过滤池

```python
import vspider

def some(url):
    print(url)
    # 同一个函数内不配置过滤池就默认以 _filter_+<函数名字> 作为表名字的数据库过滤池，
    # 比如当前这个如果没有在 @ 或 & 函数之前配置，就会生成 _filter_some 的过滤表，表内部都是以 url 加盐的 md5 存储
    # （小优化：内部实现的过滤池，是会在最长每五分钟抽一次数据库内最新四千条作为内存过滤池，如果内存里有就不用操作数据库）
    
    x | "天空" # 生成一个名为 _filter_天空 的过滤池，下面所有在 | 函数再次出现前的 @ 收集到的 url 都会用这个数据库过滤
    x @ url
    x * '//*[contains(@class,"c-container")]'
    x ** ('标题','string(./h3/a)')
    x ** ('链接','string(./h3/a/@href)')

    x | "大地" # 生成一个名为 _filter_大地 的过滤池
    x("some2") @ url
    x << ("test_int_",'string(//*[@id="page"]/strong/span[2])',lambda i:i.strip()[:20])
    
    ## 注意：如果你不想用过滤池，可以直接在收集函数开始之前，用 x | x 来将过滤池关闭

for i in range(10):
    url = f"https://www.baidu.com/s?wd=你好&pn={i*10}"
    some(url)
```

- ##### 极简的 next_url 解析接口，实现自动翻页的功能

```python
import vspider,vthread

@vthread.pool(10)
def some(url):
    print(url)
    x("真香") @ url
    x * '//*[contains(@class,"c-container")]'
    x ** ("标题",'string(./h3/a)')
    x ** ("链接",'string(./h3/a/@href)',lambda i:i[26:]) # 测试xpath获取数据的后续处理
    x ** ("简介",'string(./div)')
    x + ('//*[@id="page"]/a/@href',lambda i:'&'.join(i.split('&')[:2]))
    ## 通过重载 + 函数，将解析下一个页面的地址传入队列，通过迭代器迭代出来
    ## 解析时，获取的url如果不是以http开头的话就会自动在前面添加上start_url里面的domain
    ## 函数 + 的第二个参数就是对url进行修补的一种方法，一般来说有些url带有一些随机字符串序列
    ## 所以可以通过第二个参数，传入一个参数数量为一的函数进行对解析到的数据处理
    ## *注意：使用的时候一次迭代内只能使用一次爬取函数！（为了线程安全而牺牲的少量自由）

u = "https://www.baidu.com/s?wd=你好&pn=0"
for i in x.start_url(u): # 传入的urls可以是一个url的列表
    some(i) # 目前一次迭代只能使用一次爬取函数
```


- ##### 待处理的功能

- [ ] \*\* 和 << 按指定方法过滤，不收集某些数据。"弃函数"的考虑。
- [ ] 实现配置 request 方法，让 @ 能够在过滤去重 url 后用配置的 request 获取 html_content
- [x] 考虑实现 next url 收集与调度
