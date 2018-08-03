### python 爬虫文本数据收集库 vspider，信奉极简主义

- ##### 一个最简单的百度爬虫，以下代码就能快速收集前十页内容中每页的每个标题名字和标题链接
详细实现：以下代码会在脚本当前路径下生成 x.db 的 sqlite3 数据库文件，并且以 some 为表名（默认名字为方法名字，也可以自定义，更多用法详看后续说明），以 col_0, col_1 为列名（默认以col_x，x为数字递增，可以自定义名字和类型），首次执行会进行结构初始化，初始化只会执行一次，每次执行函数都会将收集到的数据插入数据库相应的表中。支持多表插入，也支持单个函数内多表插入。

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
    some(url)
```
- ##### 因为做到了线程安全，配合 vthread 能极大提高性能
详细实现：以下代码会在脚本当前路径下生成 x.db 的 sqlite3 数据库文件，以 title_url 为表名，以 title, url 为列名将数据插入到数据库表当中。用线程库 vthread 开启十条线程的线程池，每次函数执行都会抓取数据进行数据库插入。其中 @ 为使用该库内自带的普通 urlopen ,里面有简单的实现一些 url.query.values 的 quote 化以处理中文 key 的问题，不够强大。所以你可以使用 x & html_content 来自己生成 content 传入表解析器，同一张表格不能同时使用 @ 和 & 。

```python
import vspider,vthread

@vthread.pool(10)
def some(url):
    print(url)
    x("title_url") @ url
    x * '//*[contains(@class,"c-container")]' # * 用xpath语法收集节点，每个节点将会传递给下一级处理
    x ** ('title', 'string(./h3/a)')          # ** 对每个节点进行当前节点的xpath解析，传入title列
    x ** ('url',   'string(./h3/a/@href)')    # ** 同上，这里传入url
    
    # 解析完所有节点之后，会一次性把该页面所有收集到的数据插入数据库

for i in range(10):
    url = f"https://www.baidu.com/s?wd=你好&pn={i*10}"
    some(url)
```

- ##### 两种收集数据列的方式，以及单个函数多表插入配置的注意事项
注意，@ 和 & 为导入函数，目的是将 content 导入到函数里面，\* 和 \*\* 和<< 这三个方法为配置函数，是生成解析方式的函数，目前为了效率会将各个表的解析方式传入魔法实例 x 当中存储，这里的配置一旦生成就不能改变（后续可能会增加动态传递的列解析方式的开关），配置仅第一次有效。其中如果 \*\* 需要先用 \* 生成节点才能插入节点，另外如果节点解析方法（\* 和 \*\*）和单页解析方法（<<）混用的话注意要列名字配置全部都相同即可，或者如果都是用的默认名字，只需要数量相同即可。

```python
import vspider

def some(url):
    print(url)
    x @ url
    # 第一种收集方式是以 * 作为节点，** 作为节点下收集的内容地址的配置
    # 适用于 html table 类似的层叠结构数据
    x * '//*[contains(@class,"c-container")]'
    x ** ('标题','string(./h3/a)')
    x ** ('链接','string(./h3/a/@href)')

    # 第二种收集方式是以 << 直接作为收集的配置
    # 适用于 html 单个页面只有一组需要收集的数据的场景，目前不支持动态修改配置
    # 配置函数仅第一次配置有效
    x("some2") @ url
    x << ("test_int_",'string(//*[@id="page"]/strong/span[2])',lambda i:i.strip()[:20])

    # 默认都是以字符串形式进行收集的
    # 不过如果你想用不同的方式进行存储可以通过增加自定义名字
    # 在自定义名字后缀加上类型即可实现在数据库中存储的类型改变
    # 目前支持的后缀有：
    # _double_
    # _int_
    # _integer_
    # _str_
    # _string_
    # _date_

    # 注意：
    # 使用list或tuple配置收集结构的时候，列名和xpath是必填的
    # 另外：你不能"只写"以上几种后缀作为名字
    # ** 和 << 这两个配置函数都可以使用tuple和list传参数，其中如果第三个参数存在
    # 则将其作为xpath收集到的数据的后续处理函数，处理后的数据才会再插入数据库里面
    # 默认处理函数为 lambda i:i.strip(), 主动设置为None则什么都不做

for i in range(10):
    url = f"https://www.baidu.com/s?wd=你好&pn={i*10}"
    some(url)
```




