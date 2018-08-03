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
    # 所有列名为 col_0, col_1 的表
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
    
    x("asdf") & content
    x << ("col1",'//*[@id="1"]/h3/a[1]/@href',lambda i:i[:20])
    x << ("col0",'//*[@id="2"]/h3/a/@href')
    # 由于 vspider 自带的网页 html_content 获取的功能不够强大
    # 有时你需要通过别的库获取 html_content 然后通过 & 传入即可
    # @ 和 & 在同名表中请不要重复使用
    # 当你使用list或tuple来传递结构的时候，可以通过第三个参数来配置处理数据的函数
    # 比如上面的配置会让收集到的col1的数据会使用第三个参数的方法进行数据处理
    # 处理完之后才会输入数据库，默认参数是一个lambda i:i.strip()
    # 如果你有需要的数据，前后的空格都需要放进去，那么就写入None即可
    # 如：
    # x << ("col1",'//*[@id="1"]/h3/a[1]/@href',None)

    # 注意：
    # 两个配置表名字的中间的所有 col 配置都为前一个表的 col 配置
    # 使用list或tuple配置收集结构的时候，列名和xpath是必填的

url = 'http://www.baidu.com/s?wd=翻译'
for i in range(5):
    some(url)

##@vthread.pool(3)
##def some2(url):
##    x @ url
##    x * '//*[@class="result c-container "]'
##    x ** 'string(./h3/a)'
##    x ** 'string(./h3/a/@href)'
##    x * '//*[@class="result-op c-container"]'
##    x ** 'string(./h3/a)'
##    x ** 'string(./h3/a/@href)'
##
##url = 'http://www.baidu.com/s?wd=翻译'
##for i in range(5):
##    some2(url)




##def some3(url):
##    print(url)
##    x("真臭") @ url
##    x * '//*[contains(@class,"c-container")]'
##    x ** ("标题",'string(./h3/a)')
##    x ** ("链接",'string(./h3/a/@href)',lambda i:i[26:]) # 测试爬去数据的后续处理
##    x ** ("简介",'string(./div)')
##
##    if url.endswith("=0"):
##        x("真香") @ url
##        x << 'string(//*[@id="1"]/h3/a)'
##        x << 'string(//*[@id="2"]/h3/a)'
##
##for i in range(2):
##    url = f"https://www.baidu.com/s?wd=你好&pn={i*10}"
##    some3(url)














