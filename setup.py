from __future__ import print_function  
from setuptools import setup, find_packages  
import sys  
  
setup(  
    name="vspider",
    version="0.0.8",
    author="vilame",
    author_email="opaquism@hotmail.com",
    description="minimalist crawling framework.",
    long_description="""
Crawling framework for storing text data via sqlite3.
=====================================================

Support for xpath and jsonpath syntax

sqlite3: table_name: some, table_col: col_0, col_1
==================================================

.. code-block:: python

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

sqlite3: table_name: some,some2; table1_col: title,url; table2_col: test
========================================================================

.. code-block:: python

    import vspider,vthread 

    @vhread.pool(10) # By using the Vthread function library, the efficiency can be greatly improved.
    def some(url):
        print(url)
        x @ url
        # The first way of collecting is to use * as the node, ** as the
        # configuration of the content address collected under the node.
        # applicable to data of type html_table.
        x * '//*[contains(@class,"c-container")]'
        x ** ('title','string(./h3/a)')
        x ** ('url',  'string(./h3/a/@href)')

        # The second way of collecting is "directly collecting" by <<.
        # It is suitable for a single page to collect only one set of data
        x("some2") @ url
        x << ("test_int_",'string(//*[@id="page"]/strong/span[2])',lambda i:i[:20])
        # setting the storage type with a suffix
        # Support:
        # _double_
        # _int_
        # _integer_
        # _str_
        # _string_
        # _date_

        # Both ** and << both configuration functions can use tuple and list to pass parameters.
        # If the third parameter exists, it will be used as the subsequent processing function of
        # the data collected by xpath, and the processed data will be inserted into the database.
        # defualt function: lambda i:i.strip(),if set it None, do nothing.

    for i in range(10):
        url = f"https://www.baidu.com/s?wd=你好&pn={i*10}"
        some(url)
    
""",
    long_description_content_type="text/markdown",
    license="MIT",
    url="https://github.com/cilame/vspider",
    packages=['vspider'],
    classifiers=[
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
    ]
)  
