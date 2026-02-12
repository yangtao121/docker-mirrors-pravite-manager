#!/usr/bin/env python3
"""
Docker 私有仓库管理系统 - 界面截图脚本
使用 Selenium + Chrome 进行截图，支持中文
"""

import sys
import subprocess
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def check_chrome_installation():
    """检查 Chrome 是否安装"""
    try:
        result = subprocess.run(['google-chrome', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ 检测到 Chrome: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass

    try:
        result = subprocess.run(['chromium-browser', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ 检测到 Chromium: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass

    print("✗ 未检测到 Chrome/Chromium 浏览器")
    print("  请安装: sudo apt-get install chromium-browser")
    print("  或: sudo apt-get install google-chrome-stable")
    return False


def install_chromedriver():
    """安装或检查 chromedriver"""
    print("正在检查 chromedriver...")
    try:
        result = subprocess.run(['chromedriver', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ 检测到 chromedriver: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass

    print("正在安装 chromedriver...")
    try:
        subprocess.run(['sudo', 'apt-get', 'install', '-y', 'chromium-chromedriver'],
                      check=True, capture_output=True)
        print("✓ chromedriver 安装成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ chromedriver 安装失败: {e}")
        return False


def take_screenshot(url, output_file='screenshot.png', width=1400, height=1100, headless=False):
    """
    使用 Selenium + Chrome 截图

    Args:
        url: 要截图的网页地址
        output_file: 输出文件名
        width: 浏览器窗口宽度
        height: 浏览器窗口高度
        headless: 是否使用无头模式（False 显示浏览器窗口，True 后台运行）
    """
    print(f"目标地址: {url}")
    print(f"窗口尺寸: {width}x{height}")
    print(f"模式: {'无头模式' if headless else '桌面模式（显示浏览器窗口）'}")
    print("-" * 50)

    # 配置 Chrome 选项
    chrome_options = Options()

    # 设置中文字体
    chrome_options.add_argument('--lang=zh-CN')
    chrome_options.add_argument('--force-device-scale-factor=1')

    # 禁用一些可能导致问题的特性
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-web-security')
    chrome_options.add_argument('--disable-features=VizDisplayCompositor')

    # 设置窗口大小
    chrome_options.add_argument(f'--window-size={width},{height}')

    # 根据参数决定是否显示浏览器窗口
    if headless:
        chrome_options.add_argument('--headless=new')
    else:
        # 桌面模式，显示浏览器窗口
        print("提示: 浏览器窗口将会显示，请勿关闭...")

    # 设置用户代理
    chrome_options.add_argument(
        'user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )

    try:
        print("正在启动 Chrome 浏览器...")
        driver = webdriver.Chrome(options=chrome_options)
        print("✓ 浏览器已启动")

        # 访问目标页面
        print("正在加载页面...")
        driver.get(url)

        # 等待页面加载完成（最多 30 秒）
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'header.header'))
        )
        print("✓ 页面主体已加载")

        # 等待 5 秒让所有动态内容完全渲染
        print("等待页面完全渲染（5秒）...")
        time.sleep(5)

        # 检查健康状态
        try:
            health_text = driver.find_element(By.ID, 'healthText').text
            if health_text == '正在检查仓库状态...':
                print("等待健康状态检查...")
                time.sleep(5)
                health_text = driver.find_element(By.ID, 'healthText').text
                print(f"✓ 仓库状态: {health_text}")
        except:
            print("提示: 无法获取健康状态")

        # 再等待 2 秒确保所有动画完成
        time.sleep(2)

        # 执行截图
        print(f"正在截图，保存为 {output_file}...")
        driver.save_screenshot(output_file)
        print(f"✓ 截图成功！文件已保存: {output_file}")

        # 获取文件大小
        import os
        file_size = os.path.getsize(output_file)
        print(f"文件大小: {file_size / 1024:.1f} KB")

        return True

    except Exception as e:
        print(f"✗ 截图失败: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False

    finally:
        # 关闭浏览器
        try:
            print("正在关闭浏览器...")
            driver.quit()
            print("✓ 浏览器已关闭")
        except:
            pass


def main():
    TARGET_URL = 'http://192.168.5.249:8080'
    OUTPUT_FILE = 'screenshot.png'
    WINDOW_WIDTH = 1400
    WINDOW_HEIGHT = 1100

    # 询问是否使用桌面模式
    print("=" * 50)
    print("Docker 私有仓库管理系统 - 界面截图工具")
    print("=" * 50)
    print()
    print("请选择截图模式:")
    print("  1. 桌面模式（显示浏览器窗口，推荐调试使用）")
    print("  2. 无头模式（后台运行，不显示窗口）")
    print()

    try:
        choice = input("请输入选项 [1/2，默认=1]: ").strip() or "1"
        headless = (choice == "2")
    except (EOFError, KeyboardInterrupt):
        # 如果无法交互输入，默认使用无头模式
        headless = False

    print()
    print("=" * 50)

    # 检查浏览器
    if not check_chrome_installation():
        sys.exit(1)

    # 检查/安装 chromedriver
    if not install_chromedriver():
        print("\n提示: 也可以手动安装 chromedriver")
        print("  wget https://chromedriver.storage.googleapis.com/...")
        sys.exit(1)

    print()
    print("=" * 50)
    print("开始截图...")
    print("=" * 50)
    print()

    success = take_screenshot(
        url=TARGET_URL,
        output_file=OUTPUT_FILE,
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        headless=headless
    )

    print()
    print("=" * 50)
    if success:
        print("✓ 截图任务完成！")
    else:
        print("✗ 截图任务失败")
    print("=" * 50)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
