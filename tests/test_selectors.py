from playwright.sync_api import sync_playwright

def test_selectors():
    """测试AWS新闻列表页的XPath选择器"""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        page = browser.new_page()
        
        # 访问AWS新闻页面
        url = "https://aws.amazon.com/cn/about-aws/whats-new/networking_and_content_delivery/?whats-new-content.sort-by=item.additionalFields.postDateTime&whats-new-content.sort-order=desc&awsf.whats-new-products=*all"
        page.goto(url)
        
        # 等待页面加载
        page.wait_for_load_state('networkidle')
        print(f"当前页面URL: {page.url}")
        
        # 测试文章列表选择器
        articles_selector = "xpath=/html/body/div[2]/main/div[3]/div[2]/div[2]/div[4]/section/ul/li"
        articles = page.query_selector_all(articles_selector)
        print(f"找到 {len(articles)} 个文章")
        
        # 如果找到文章，打印第一篇文章的信息
        if len(articles) > 0:
            first_article = articles[0]
            print("第一篇文章文本:", first_article.inner_text())
            
            # 尝试获取文章链接
            link = first_article.query_selector("a")
            if link:
                href = link.get_attribute("href")
                print("文章链接:", href)
        else:
            print("未找到任何文章，尝试获取页面内容...")
            print("页面标题:", page.title())
            
            # 检查是否有ul元素
            uls = page.query_selector_all("ul")
            print(f"页面中有 {len(uls)} 个ul元素")
            
            # 检查原始选择器的每一部分
            parts = articles_selector.replace("xpath=", "").split("/")
            path = ""
            for i, part in enumerate(parts):
                if not part:
                    continue
                path += "/" + part
                if i > 2:  # 跳过前面的html/body等通用部分
                    elements = page.query_selector_all(f"xpath={path}")
                    print(f"路径 '{path}' 匹配了 {len(elements)} 个元素")
        
        # 测试分页按钮选择器
        next_button_selector = "xpath=/html/body/div[2]/main/div[3]/div[2]/div[2]/div[5]/a[4]"
        next_button = page.query_selector(next_button_selector)
        print(f"下一页按钮存在: {next_button is not None}")
        
        if next_button:
            print("下一页按钮文本:", next_button.inner_text())
        else:
            print("未找到下一页按钮，尝试查找所有分页元素...")
            pagination_links = page.query_selector_all("a[aria-label*='Page']")
            print(f"找到 {len(pagination_links)} 个分页链接")
            for i, link in enumerate(pagination_links):
                print(f"分页链接 {i+1} 文本: {link.inner_text()}")
        
        # 关闭浏览器
        page.close()
        browser.close()

if __name__ == "__main__":
    test_selectors() 