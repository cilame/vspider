import vthread
import vspider

# vspider 是一个使用 sqlite 对轻量级文本进行数据收集的爬虫库
# 线程安全，配合 vthread 相当方便

@vthread.pool(3) # 开三个线程池
def some(url):
    print(url)
    x @ url
    x << 'string(//*[@id="1"]/h3/a[1])'
    x << '//*[@id="2"]/h3/a/text()'
    # 最简化：
    # 以上方法将会在 sqlite 里面生成一个表名为 some（默认用函数名字），
    # 所有列名为 some_col_0, some_col_1 的表
    # 每次执行该函数就会用默认的函数对 url 解析获取其content
    # 然后以各列的 xpath 解析 content 获取录入数据
    
    x("foo") @ url
    x << ("col1",'//*[@id="1"]/h3/a[1]/@href')
    x << ("col2",'//*[@id="2"]/h3/a/@href')
    # 可配置：
    # 以上方法将会在 sqlite 里面生成一个表名为 foo，
    # 所有列名为 col1, col2 的表
    # 每次执行该函数就会用默认的函数对 url 解析获取其content
    # 然后以各列的 xpath 解析 content 获取录入数据
    # 且到这里，some 表和 foo 表以及表收集的数据互不干扰


    import requests
    content = requests.get(url).content
    
    x("asdf") < content
    # 由于 vspider 自带的网页 html_content 获取的功能不够强大
    # 有时你需要通过别的库获取 html_content 然后通过 < 传入即可
    # @ 和 < 在同名表中请不要重复使用

    # 注意：
    # 两个配置表名字的中间的所有 col 配置都为前一个表的 col 配置

url = "http://www.baidu.com/s?wd=你好"
for i in range(5):
    some(url)

