from playwright.sync_api import sync_playwright
import json

def test_xpath():
    """测试不同的XPath选择器来提取AWS新闻页面的文章链接"""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        page = browser.new_page()
        
        # 访问AWS新闻页面
        url = "https://aws.amazon.com/cn/about-aws/whats-new/networking_and_content_delivery/?whats-new-content.sort-by=item.additionalFields.postDateTime&whats-new-content.sort-order=desc&awsf.whats-new-products=*all"
        page.goto(url)
        
        # 等待页面加载
        page.wait_for_load_state('networkidle')
        print(f"当前页面URL: {page.url}")
        
        # 测试选择器1: 直接提取列表项内的所有链接
        xpath1 = "xpath=/html/body/div[2]/main/div[3]/div[2]/div[2]/div[4]/section/ul/li//a"
        links1 = page.query_selector_all(xpath1)
        print(f"\n选择器1 '{xpath1}' 找到 {len(links1)} 个链接")
        
        if len(links1) > 0:
            print("前3个链接:")
            for i, link in enumerate(links1[:3]):
                href = link.get_attribute("href")
                text = link.inner_text()
                print(f"{i+1}. {text} -> {href}")
        
        # 测试选择器2: 使用列表项中的标题div里的链接
        xpath2 = "xpath=/html/body/div[2]/main/div[3]/div[2]/div[2]/div[4]/section/ul/li/div[contains(@class, 'm-card-title')]/a"
        links2 = page.query_selector_all(xpath2)
        print(f"\n选择器2 '{xpath2}' 找到 {len(links2)} 个链接")
        
        if len(links2) > 0:
            print("前3个链接:")
            for i, link in enumerate(links2[:3]):
                href = link.get_attribute("href")
                text = link.inner_text()
                print(f"{i+1}. {text} -> {href}")
        
        # 这个选择器是基于用户提供的原始列表项选择器, 但寻找其内部有href属性的链接元素
        xpath3 = "xpath=/html/body/div[2]/main/div[3]/div[2]/div[2]/div[4]/section/ul/li[1]/div[1]/a"
        link3 = page.query_selector(xpath3)
        print(f"\n选择器3 '{xpath3}' 找到: {link3 is not None}")
        
        if link3:
            print(f"链接: {link3.inner_text()} -> {link3.get_attribute('href')}")
            
            # 测试这个具体选择器是否可以在所有列表项上匹配
            test_general = "xpath=/html/body/div[2]/main/div[3]/div[2]/div[2]/div[4]/section/ul/li/div[1]/a"
            all_links = page.query_selector_all(test_general)
            print(f"\n泛化选择器 '{test_general}' 找到 {len(all_links)} 个链接")
            
            if len(all_links) > 2:
                print(f"第1个: {all_links[0].inner_text()} -> {all_links[0].get_attribute('href')}")
                print(f"第2个: {all_links[1].inner_text()} -> {all_links[1].get_attribute('href')}")
                print(f"最后一个: {all_links[-1].inner_text()} -> {all_links[-1].get_attribute('href')}")
        
        print("\n建议用于工作流的选择器:")
        print("1. 获取文章项中标题链接: xpath=/html/body/div[2]/main/div[3]/div[2]/div[2]/div[4]/section/ul/li/div[1]/a")
        print("2. 获取文章日期: xpath=/html/body/div[2]/main/div[3]/div[2]/div[2]/div[4]/section/ul/li/div[2]")
        print("3. 下一页按钮: xpath=/html/body/div[2]/main/div[3]/div[2]/div[2]/div[5]/a[4]")
        
        # 关闭浏览器
        page.close()
        browser.close()

if __name__ == "__main__":
    test_xpath() 