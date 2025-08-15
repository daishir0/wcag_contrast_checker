#!/usr/bin/env python3
# WCAG Contrast Checker (WCAG 1.4.3, 1.4.6)
# ==========================================
#
# 使い方 (Usage):
#   python /home/ec2-user/app/a11y/wcag_contrast_checker/wcag_contrast_checker.py [URL]
#
# 説明:
#   このツールはWebページをチェックして、テキストのコントラスト比（WCAG 1.4.3, 1.4.6）を
#   評価します。ページ上のすべてのテキスト要素を検出し、前景色と背景色のコントラスト比を
#   計算して、WCAGガイドラインに準拠しているかを判定します。
#
# 出力:
#   - コマンドラインに詳細なレポートを表示
#     - コントラスト比が適切な要素のリスト
#     - コントラスト比が不適切な要素のリスト
#     - WCAG 1.4.3/1.4.6への準拠状況
#
# 必要条件:
#   - Python 3.7以上
#   - Chrome/Chromiumブラウザ
#   - ChromeDriver
#   - Anthropic API キー（config.pyに設定）
#   - 依存パッケージ（requirements.txtに記載）

import sys
import time
import json
import base64
import os
import tempfile
import shutil
import re
import math
from io import BytesIO
from PIL import Image
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from config import CHROME_BINARY_PATH, CHROME_DRIVER_PATH, DEBUG

def setup_driver():
    """
    Set up and return a Chrome WebDriver instance
    """
    options = Options()
    # サーバー環境では必ずヘッドレスモードで実行
    options.binary_location = CHROME_BINARY_PATH
    options.add_argument("--window-size=1366,768")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-software-rasterizer')
    options.add_argument('--disable-infobars')
    options.add_argument('--headless=new')
    options.add_argument('--disable-setuid-sandbox')
    options.add_argument('--no-first-run')
    options.add_argument('--no-default-browser-check')
    options.add_argument('--disable-background-networking')
    options.add_argument('--disable-prompt-on-repost')
    options.add_argument('--disable-sync')
    
    # Use a dedicated temporary directory for Chrome data
    temp_dir = tempfile.mkdtemp()
    options.add_argument(f'--user-data-dir={temp_dir}')
    options.add_argument('--data-path=' + os.path.join(temp_dir, 'data'))
    options.add_argument('--homedir=' + os.path.join(temp_dir, 'home'))
    options.add_argument('--disk-cache-dir=' + os.path.join(temp_dir, 'cache'))

    # ChromeDriverの設定
    service = Service(executable_path=CHROME_DRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    return driver, temp_dir

def cleanup_temp_dir(temp_dir):
    """
    Clean up temporary directory after the driver is closed
    """
    try:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
            print(f"一時ディレクトリを削除しました: {temp_dir}")
    except Exception as e:
        print(f"警告: 一時ディレクトリの削除に失敗しました: {e}")

def get_text_elements(driver):
    """
    Get all text elements from the page
    """
    # JavaScript to extract text elements with their computed styles
    script = """
    function getTextElements() {
        const elements = [];
        const walker = document.createTreeWalker(
            document.body,
            NodeFilter.SHOW_TEXT,
            {
                acceptNode: function(node) {
                    // Skip whitespace-only text nodes
                    if (node.textContent.trim().length === 0) {
                        return NodeFilter.FILTER_REJECT;
                    }
                    
                    const parent = node.parentElement;
                    if (!parent) return NodeFilter.FILTER_REJECT;
                    
                    // Skip hidden elements
                    const style = window.getComputedStyle(parent);
                    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
                        return NodeFilter.FILTER_REJECT;
                    }
                    
                    // Skip script and style elements
                    const tagName = parent.tagName.toLowerCase();
                    if (['script', 'style', 'noscript'].includes(tagName)) {
                        return NodeFilter.FILTER_REJECT;
                    }
                    
                    return NodeFilter.FILTER_ACCEPT;
                }
            }
        );
        
        let node;
        while (node = walker.nextNode()) {
            const parent = node.parentElement;
            const style = window.getComputedStyle(parent);
            const rect = parent.getBoundingClientRect();
            
            // Skip elements that are not visible
            if (rect.width === 0 || rect.height === 0) continue;
            
            // Get text content
            const text = node.textContent.trim();
            if (text.length === 0) continue;
            
            // Check if this is part of inactive UI, decorative, logo, or image text
            const isInactiveUI = parent.disabled || parent.getAttribute('aria-disabled') === 'true' || 
                               style.pointerEvents === 'none';
            const isDecorative = parent.getAttribute('aria-hidden') === 'true' || 
                                parent.getAttribute('role') === 'presentation';
            const isLogo = parent.closest('[role="banner"]') || parent.closest('.logo') || 
                          parent.closest('#logo') || /logo/i.test(parent.className);
            const isImageText = parent.tagName.toLowerCase() === 'img' || 
                               style.backgroundImage !== 'none';
            
            // Skip excluded elements
            if (isInactiveUI || isDecorative || isLogo || isImageText) {
                continue;
            }
            
            // Get font properties
            const fontSize = parseFloat(style.fontSize);
            const fontWeight = style.fontWeight;
            const isBold = fontWeight === 'bold' || fontWeight === 'bolder' || parseInt(fontWeight) >= 700;
            
            // Get colors
            const color = style.color;
            const backgroundColor = style.backgroundColor;
            
            // Get language
            const lang = parent.lang || parent.closest('[lang]')?.lang || document.documentElement.lang || 'en';
            const isJapanese = /^ja/i.test(lang);
            
            // Generate XPath
            function getXPath(element) {
                if (element.id !== '') {
                    return '//*[@id="' + element.id + '"]';
                }
                if (element === document.body) {
                    return '/html/body';
                }
                
                let index = 0;
                const siblings = element.parentNode.childNodes;
                for (let i = 0; i < siblings.length; i++) {
                    const sibling = siblings[i];
                    if (sibling === element) {
                        return getXPath(element.parentNode) + '/' + element.tagName.toLowerCase() + '[' + (index + 1) + ']';
                    }
                    if (sibling.nodeType === 1 && sibling.tagName === element.tagName) {
                        index++;
                    }
                }
            }
            
            elements.push({
                text: text,
                tagName: parent.tagName,
                id: parent.id || '',
                className: parent.className || '',
                xpath: getXPath(parent),
                fontSize: fontSize,
                fontWeight: fontWeight,
                isBold: isBold,
                color: color,
                backgroundColor: backgroundColor,
                language: isJapanese ? 'ja' : 'en',
                rect: {
                    x: rect.x,
                    y: rect.y,
                    width: rect.width,
                    height: rect.height
                }
            });
        }
        
        return elements;
    }
    
    return getTextElements();
    """
    
    elements = driver.execute_script(script)
    print(f"テキスト要素を {len(elements)} 個検出しました")
    return elements

def rgb_to_luminance(rgb_str):
    """
    Convert RGB color string to relative luminance
    """
    # Parse RGB values
    rgb_match = re.match(r'rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*[\d.]+)?\)', rgb_str)
    if not rgb_match:
        # Try hex format
        hex_match = re.match(r'#([0-9a-fA-F]{6})', rgb_str)
        if hex_match:
            hex_val = hex_match.group(1)
            r = int(hex_val[0:2], 16)
            g = int(hex_val[2:4], 16)
            b = int(hex_val[4:6], 16)
        else:
            # Default to black if parsing fails
            r, g, b = 0, 0, 0
    else:
        r, g, b = int(rgb_match.group(1)), int(rgb_match.group(2)), int(rgb_match.group(3))
    
    # Convert to relative luminance
    def gamma_correct(c):
        c = c / 255.0
        if c <= 0.03928:
            return c / 12.92
        else:
            return math.pow((c + 0.055) / 1.055, 2.4)
    
    r_linear = gamma_correct(r)
    g_linear = gamma_correct(g)
    b_linear = gamma_correct(b)
    
    luminance = 0.2126 * r_linear + 0.7152 * g_linear + 0.0722 * b_linear
    return luminance

def calculate_contrast_ratio(foreground_color, background_color):
    """
    Calculate contrast ratio between foreground and background colors
    """
    fg_luminance = rgb_to_luminance(foreground_color)
    bg_luminance = rgb_to_luminance(background_color)
    
    # Ensure L1 is the lighter color
    l1 = max(fg_luminance, bg_luminance)
    l2 = min(fg_luminance, bg_luminance)
    
    contrast_ratio = (l1 + 0.05) / (l2 + 0.05)
    return contrast_ratio

def determine_wcag_compliance(element, contrast_ratio):
    """
    Determine WCAG compliance based on element properties and contrast ratio
    """
    font_size_pt = element['fontSize'] * 0.75  # Convert px to pt (approximate)
    is_bold = element['isBold']
    is_japanese = element['language'] == 'ja'
    
    # Determine if it's large text
    if is_japanese:
        # Japanese text criteria
        if is_bold:
            is_large_text = font_size_pt >= 18 or font_size_pt >= 22
        else:
            is_large_text = font_size_pt >= 14 or font_size_pt >= 18
    else:
        # English text criteria
        if is_bold:
            is_large_text = font_size_pt >= 18 or font_size_pt >= 22
        else:
            is_large_text = font_size_pt >= 14 or font_size_pt >= 18
    
    # Determine required contrast ratio
    if is_large_text:
        required_ratio = 3.0  # Situation B
        situation = "B"
    else:
        required_ratio = 4.5  # Situation A
        situation = "A"
    
    is_compliant = contrast_ratio >= required_ratio
    
    return {
        'is_compliant': is_compliant,
        'required_ratio': required_ratio,
        'actual_ratio': contrast_ratio,
        'situation': situation,
        'is_large_text': is_large_text,
        'font_size_pt': font_size_pt
    }

def check_contrast_ratio(url):
    """
    Check contrast ratios on a webpage
    """
    try:
        print("Chrome WebDriverを設定中...")
        driver, temp_dir = setup_driver()
        print(f"Chrome WebDriverの設定が完了しました。一時ディレクトリ: {temp_dir}")
    except Exception as e:
        print(f"Chrome WebDriverの設定エラー: {e}")
        if "DevToolsActivePort file doesn't exist" in str(e):
            print("\nDevToolsActivePortエラーのトラブルシューティング:")
            print("1. Chromeがインストールされており、実行可能であることを確認してください")
            print("2. 実行中のChromeプロセスがないか確認してください")
            print("3. config.pyのChrome実行ファイルパスが正しいか確認してください")
            print(f"4. 現在のChrome実行ファイルパス: {CHROME_BINARY_PATH}")
            print(f"5. 現在のChromeDriverパス: {CHROME_DRIVER_PATH}")
            print("6. 既存のChromeプロセスを終了してみてください: pkill -f chrome")
        raise
    
    try:
        # Navigate to URL
        print(f"URLに移動中: {url}")
        driver.get(url)
        
        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        print("ページの読み込みが完了しました")
        
        # Get all text elements
        text_elements = get_text_elements(driver)
        
        # Process each element
        results = []
        for i, element in enumerate(text_elements):
            print(f"要素を処理中 {i+1}/{len(text_elements)}: {element['text'][:50]}...")
            
            # Calculate contrast ratio
            contrast_ratio = calculate_contrast_ratio(element['color'], element['backgroundColor'])
            
            # Determine WCAG compliance
            compliance = determine_wcag_compliance(element, contrast_ratio)
            
            # Create result object
            result = {
                'index': i,
                'text': element['text'][:100],  # Limit text length
                'tagName': element['tagName'],
                'id': element['id'],
                'className': element['className'],
                'xpath': element['xpath'],
                'fontSize': element['fontSize'],
                'fontWeight': element['fontWeight'],
                'isBold': element['isBold'],
                'color': element['color'],
                'backgroundColor': element['backgroundColor'],
                'language': element['language'],
                'contrast_ratio': round(contrast_ratio, 2),
                'compliance': compliance
            }
            
            results.append(result)
        
        # Create final report
        compliant_elements = [r for r in results if r['compliance']['is_compliant']]
        non_compliant_elements = [r for r in results if not r['compliance']['is_compliant']]
        
        final_report = {
            "url": url,
            "total_text_elements": len(results),
            "compliant_elements": len(compliant_elements),
            "non_compliant_elements": len(non_compliant_elements),
            "compliant_list": compliant_elements,
            "non_compliant_list": non_compliant_elements,
            "wcag_1_4_3_compliant": len(non_compliant_elements) == 0
        }
        
        return final_report
        
    finally:
        driver.quit()
        cleanup_temp_dir(temp_dir)

def main():
    if len(sys.argv) != 2:
        print("Usage: python wcag_contrast_checker.py url")
        sys.exit(1)

    url = sys.argv[1]
    
    try:
        # Check contrast ratios
        print(f"{url} のコントラスト比チェックを開始")
        results = check_contrast_ratio(url)
        
        # Print detailed results to console
        print("\n======================================")
        print("WCAG 1.4.3/1.4.6 コントラスト比 分析レポート")
        print("======================================")
        print(f"URL: {url}")
        print(f"テキスト要素の合計: {results['total_text_elements']}")
        print(f"適切なコントラスト比の要素: {results['compliant_elements']}")
        print(f"不適切なコントラスト比の要素: {results['non_compliant_elements']}")
        print(f"WCAG 1.4.3 準拠状況: {'準拠' if results['wcag_1_4_3_compliant'] else '非準拠'}")
        
        # Print non-compliant elements
        if not results['wcag_1_4_3_compliant']:
            print("\n== コントラスト比が不適切な要素 ==")
            for element in results['non_compliant_list']:
                print(f"\n要素 {element['index']}: {element['tagName']}")
                print(f"  テキスト: {element['text']}")
                print(f"  ID: {element['id'] or 'なし'}")
                print(f"  クラス: {element['className'] or 'なし'}")
                print(f"  XPath: {element['xpath']}")
                print(f"  フォントサイズ: {element['fontSize']}px ({element['compliance']['font_size_pt']:.1f}pt)")
                print(f"  フォントウェイト: {element['fontWeight']} ({'太字' if element['isBold'] else '通常'})")
                print(f"  言語: {element['language']}")
                print(f"  前景色: {element['color']}")
                print(f"  背景色: {element['backgroundColor']}")
                print(f"  コントラスト比: {element['contrast_ratio']}:1")
                print(f"  必要なコントラスト比: {element['compliance']['required_ratio']}:1 (状況{element['compliance']['situation']})")
                print(f"  大きなテキスト: {'はい' if element['compliance']['is_large_text'] else 'いいえ'}")
                print(f"  推奨事項: コントラスト比を{element['compliance']['required_ratio']}:1以上に改善してください")
        
        # Print compliant elements summary
        print(f"\n== 適切なコントラスト比の要素: {results['compliant_elements']}個 ==")
        if results['compliant_elements'] > 0:
            situation_a_count = len([e for e in results['compliant_list'] if e['compliance']['situation'] == 'A'])
            situation_b_count = len([e for e in results['compliant_list'] if e['compliance']['situation'] == 'B'])
            print(f"  状況A (4.5:1以上): {situation_a_count}個")
            print(f"  状況B (3:1以上): {situation_b_count}個")
        
        # Print summary statistics
        if results['total_text_elements'] > 0:
            compliance_rate = (results['compliant_elements'] / results['total_text_elements']) * 100
            print(f"\n== 統計情報 ==")
            print(f"準拠率: {compliance_rate:.1f}%")
            
            # Language breakdown
            ja_elements = len([e for e in results['compliant_list'] + results['non_compliant_list'] if e['language'] == 'ja'])
            en_elements = len([e for e in results['compliant_list'] + results['non_compliant_list'] if e['language'] == 'en'])
            print(f"日本語要素: {ja_elements}個")
            print(f"英語要素: {en_elements}個")
        
    except Exception as e:
        print(f"エラー: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()