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
import csv
from urllib.parse import urlparse
import numpy as np
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
from sklearn.cluster import KMeans
from config import CHROME_BINARY_PATH, CHROME_DRIVER_PATH, DEBUG, PAGE_LOAD_WAIT_TIME, SAVE_SCREENSHOTS, SCREENSHOT_DIR

def setup_driver():
    """
    Set up and return a Chrome WebDriver instance
    """
    options = Options()
    # サーバー環境では必ずヘッドレスモードで実行
    options.binary_location = CHROME_BINARY_PATH
    options.add_argument("--window-size=1920,1080")
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

def url_to_filename(url):
    """
    Convert URL to a safe filename
    """
    parsed = urlparse(url)

    # ドメインを取得
    domain = parsed.netloc

    # 不要なプレフィックスを除去
    domain = domain.replace('www.', '')

    # ファイル名に使用できない文字を置換
    safe_chars = re.sub(r'[^\w\-_.]', '_', domain)

    # 連続するアンダースコアを単一にする
    safe_chars = re.sub(r'_+', '_', safe_chars)

    # 前後のアンダースコアを除去
    safe_chars = safe_chars.strip('_')

    return safe_chars

def export_to_csv(results, url):
    """
    Export results to CSV file
    """
    filename = f"wcag_results_{url_to_filename(url)}.csv"

    # すべての要素（適切 + 不適切）を結合
    all_elements = []

    # 適切な要素を追加
    for element in results['compliant_list']:
        all_elements.append({
            '判定': '適切',
            '要素番号': element['index'],
            'タグ種別': element['tagName'],
            'テキスト': element['text'],
            'ID': element['id'] if element['id'] else '',
            'クラス': element['className'] if element['className'] else '',
            'XPath': element['xpath'],
            'フォントサイズ(px)': element['fontSize'],
            'フォントウェイト': element['fontWeight'],
            '前景色': element['color'],
            '背景色': element['backgroundColor'],
            '真背景色': f"rgb{element['true_background_rgb']}" if element.get('true_background_rgb') else '',
            'コントラスト比': element['final_contrast_ratio'],
            '必要コントラスト比': element['compliance']['required_ratio'],
            '状況': element['compliance']['situation'],
            '大きなテキスト': '〇' if element['compliance']['is_large_text'] else '×',
            '言語': element['language']
        })

    # 不適切な要素を追加
    for element in results['non_compliant_list']:
        all_elements.append({
            '判定': '不適切',
            '要素番号': element['index'],
            'タグ種別': element['tagName'],
            'テキスト': element['text'],
            'ID': element['id'] if element['id'] else '',
            'クラス': element['className'] if element['className'] else '',
            'XPath': element['xpath'],
            'フォントサイズ(px)': element['fontSize'],
            'フォントウェイト': element['fontWeight'],
            '前景色': element['color'],
            '背景色': element['backgroundColor'],
            '真背景色': f"rgb{element['true_background_rgb']}" if element.get('true_background_rgb') else '',
            'コントラスト比': element['final_contrast_ratio'],
            '必要コントラスト比': element['compliance']['required_ratio'],
            '状況': element['compliance']['situation'],
            '大きなテキスト': '〇' if element['compliance']['is_large_text'] else '×',
            '言語': element['language']
        })

    # 要素番号でソート
    all_elements.sort(key=lambda x: x['要素番号'])

    # CSVファイルに書き込み
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            if all_elements:
                fieldnames = all_elements[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                # ヘッダー行を書き込み
                writer.writeheader()

                # データ行を書き込み
                writer.writerows(all_elements)

        print(f"\nCSVファイルを出力しました: {filename}")
        print(f"出力要素数: {len(all_elements)}個")

    except Exception as e:
        print(f"CSVファイル出力エラー: {e}")

    return filename

def get_text_elements(driver):
    """
    Get all text elements from the page
    """
    # Remove cookie banners BEFORE extracting text elements
    if DEBUG:
        print("テキスト要素検出前にCookieバナーを除去中...")
    comprehensive_banner_removal(driver)

    # ページの完全な読み込みを待つ
    if DEBUG:
        print(f"ページの読み込み完了を待機中... ({PAGE_LOAD_WAIT_TIME}秒)")
    time.sleep(PAGE_LOAD_WAIT_TIME)

    # JavaScriptの実行が完了するまで待つ
    driver.execute_script("return document.readyState") == "complete"

    # ネットワーク活動の完了を確認
    try:
        driver.set_script_timeout(30)
        wait_script = """
        const callback = arguments[arguments.length - 1];
        if (typeof performance !== 'undefined') {
            // 200ms間新しいリソース読み込みがなければ完了とみなす
            let lastCount = performance.getEntriesByType('resource').length;
            const checkInterval = setInterval(() => {
                const currentCount = performance.getEntriesByType('resource').length;
                if (currentCount === lastCount) {
                    clearInterval(checkInterval);
                    callback(true);
                }
                lastCount = currentCount;
            }, 200);
            // タイムアウト処理（5秒）
            setTimeout(() => {
                clearInterval(checkInterval);
                callback(true);
            }, 5000);
        } else {
            callback(true);
        }
        """
        driver.execute_async_script(wait_script)
        if DEBUG:
            print("ネットワーク活動の完了を確認しました")
    except Exception as e:
        if DEBUG:
            print(f"ネットワーク活動の確認でエラー: {e}")

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

def srgb_to_linear(color_value):
    """
    Convert sRGB color value to linear RGB
    """
    color_value = color_value / 255.0
    if color_value <= 0.03928:
        return color_value / 12.92
    else:
        return math.pow((color_value + 0.055) / 1.055, 2.4)

def linear_rgb_to_luminance(r_linear, g_linear, b_linear):
    """
    Convert linear RGB to relative luminance
    """
    return 0.2126 * r_linear + 0.7152 * g_linear + 0.0722 * b_linear

def remove_known_cookie_services(driver):
    """
    Remove known cookie consent services
    """
    services = {
        'cookiebot': ['#CybotCookiebotDialog', '.CybotCookiebotDialog'],
        'onetrust': ['#onetrust-banner-sdk', '.onetrust-pc-dark-filter'],
        'cookielaw': ['#cookieChoiceInfo', '.cc-banner'],
        'quantcast': ['.qc-cmp2-container', '.qc-cmp2-footer'],
        'trustarc': ['#truste-consent-track', '.truste_popframe'],
        'iubenda': ['.iubenda-cs-overlay', '.iubenda-banner']
    }

    removed_total = 0
    for service, selectors in services.items():
        for selector in selectors:
            try:
                removed = driver.execute_script(f"""
                    const elements = document.querySelectorAll('{selector}');
                    elements.forEach(el => el.remove());
                    return elements.length;
                """)
                removed_total += removed
            except:
                pass

    return removed_total

def remove_cookie_banners(driver):
    """
    Remove general cookie banners
    """
    cookie_selectors = [
        '[id*="cookie"]', '[class*="cookie"]',
        '[id*="consent"]', '[class*="consent"]',
        '[id*="gdpr"]', '[class*="gdpr"]',
        '[id*="privacy"]', '[class*="privacy"]',
        '[class*="banner"]', '[class*="overlay"]',
        '[class*="modal"]', '[class*="popup"]',
        '#cookieChoiceInfo', '.cookie-notice',
        '.gdpr-banner', '.consent-banner',
        '.cc-banner', '.cookie-bar'
    ]

    script = """
    const selectors = arguments[0];
    let removed = 0;
    selectors.forEach(selector => {
        try {
            document.querySelectorAll(selector).forEach(el => {
                el.remove();
                removed++;
            });
        } catch(e) {
            // Ignore selector errors
        }
    });
    return removed;
    """

    try:
        removed = driver.execute_script(script, cookie_selectors)
        return removed
    except:
        return 0

def remove_cookie_content_by_text(driver):
    """
    Remove elements containing cookie-related text content
    """
    script = """
    const cookieKeywords = [
        'cookie', 'cookies', 'クッキー',
        'consent', 'gdpr', 'privacy',
        'accept', 'agree', 'decline',
        'このウェブサイトはcookieを使用',
        'cookieを使用します',
        'より良いサービス・閲覧体験',
        'cookieについて',
        'cookie policy',
        'privacy policy'
    ];

    let removed = 0;
    const elements = Array.from(document.querySelectorAll('*'));

    elements.forEach(el => {
        try {
            const text = el.textContent.toLowerCase();
            const hasId = el.id && cookieKeywords.some(keyword =>
                el.id.toLowerCase().includes(keyword.toLowerCase())
            );
            const hasClass = el.className && cookieKeywords.some(keyword =>
                el.className.toLowerCase().includes(keyword.toLowerCase())
            );
            const hasText = cookieKeywords.some(keyword =>
                text.includes(keyword.toLowerCase())
            );

            // Cookie関連の要素を特定
            if (hasId || hasClass || hasText) {
                const style = window.getComputedStyle(el);

                // 削除条件：
                // 1. 非表示でない
                // 2. テキストを含む
                // 3. html/body/head/link/style以外（CSSを保護）
                if (
                    style.display !== 'none' &&
                    style.visibility !== 'hidden' &&
                    text.trim().length > 0 &&
                    !['HTML', 'BODY', 'HEAD', 'LINK', 'STYLE'].includes(el.tagName) &&
                    (
                        // 強いCookie指標
                        hasId || hasClass ||
                        // または複数のCookieキーワードを含む
                        cookieKeywords.filter(keyword => text.includes(keyword.toLowerCase())).length >= 2 ||
                        // または特定の長いCookieフレーズを含む
                        text.includes('このウェブサイトはcookieを使用') ||
                        text.includes('より良いサービス・閲覧体験') ||
                        text.includes('cookie policy') ||
                        text.includes('privacy policy')
                    )
                ) {
                    // 親要素も含めて削除を検討
                    let targetElement = el;

                    // もし親要素もCookie関連なら親を削除
                    // ただしHEADタグは除外してCSSを保護
                    if (el.parentElement && !['HEAD'].includes(el.parentElement.tagName)) {
                        const parentText = el.parentElement.textContent.toLowerCase();
                        const parentHasCookie = cookieKeywords.some(keyword =>
                            parentText.includes(keyword.toLowerCase())
                        );
                        const parentHasClass = el.parentElement.className &&
                            cookieKeywords.some(keyword =>
                                el.parentElement.className.toLowerCase().includes(keyword.toLowerCase())
                            );

                        if (parentHasCookie || parentHasClass) {
                            targetElement = el.parentElement;
                        }
                    }

                    targetElement.remove();
                    removed++;
                }
            }
        } catch(e) {
            // Ignore errors
        }
    });

    return removed;
    """

    try:
        return driver.execute_script(script)
    except:
        return 0

def remove_high_zindex_overlays(driver):
    """
    Remove high z-index overlays that are likely cookie banners
    """
    script = """
    const elements = Array.from(document.querySelectorAll('*'));
    let removed = 0;

    elements.forEach(el => {
        try {
            const style = window.getComputedStyle(el);
            const zIndex = parseInt(style.zIndex);
            const position = style.position;
            const display = style.display;

            if (
                (position === 'fixed' || position === 'absolute') &&
                (zIndex > 100 || zIndex === 999999 || zIndex === 9999) &&
                display !== 'none' &&
                el.offsetWidth > 100 && el.offsetHeight > 50
            ) {
                const text = el.textContent.toLowerCase();
                const cookieKeywords = ['cookie', 'consent', 'gdpr', 'privacy', 'accept', 'agree'];

                if (cookieKeywords.some(keyword => text.includes(keyword))) {
                    el.remove();
                    removed++;
                }
            }
        } catch(e) {
            // Ignore errors
        }
    });

    return removed;
    """

    try:
        return driver.execute_script(script)
    except:
        return 0

def comprehensive_banner_removal(driver):
    """
    Comprehensive cookie banner removal
    """
    if DEBUG:
        print("  Cookieバナー除去を実行中...")

    # 1. Remove known services
    removed1 = remove_known_cookie_services(driver)

    # 2. Remove general selectors
    removed2 = remove_cookie_banners(driver)

    # 3. Remove high z-index elements
    removed3 = remove_high_zindex_overlays(driver)

    # 4. Remove cookie content by text (新しい汎用的手法)
    removed4 = remove_cookie_content_by_text(driver)

    # 5. Remove suspicious body children
    try:
        removed5 = driver.execute_script("""
            let removed = 0;
            try {
                Array.from(document.body.children).forEach(el => {
                    const style = window.getComputedStyle(el);
                    const text = el.textContent.toLowerCase();

                    if (
                        (style.position === 'fixed' || style.position === 'absolute') &&
                        (text.includes('cookie') || text.includes('consent') ||
                         text.includes('accept') || text.includes('gdpr')) &&
                        el.offsetHeight > 30
                    ) {
                        el.remove();
                        removed++;
                    }
                });
            } catch(e) {
                // Ignore errors
            }
            return removed;
        """)
    except:
        removed5 = 0

    total_removed = removed1 + removed2 + removed3 + removed4 + removed5

    if DEBUG and total_removed > 0:
        print(f"  Cookieバナー {total_removed}個を除去しました")
        time.sleep(1)  # Wait after removal

    return total_removed

def capture_element_screenshot(driver, element):
    """
    Capture screenshot of a specific element
    """
    try:
        # Scroll element into view
        driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", element)
        time.sleep(1)

        # Remove cookie banners before taking screenshot
        comprehensive_banner_removal(driver)

        # Get element screenshot as PNG bytes
        element_png = element.screenshot_as_png

        # Convert to PIL Image
        image = Image.open(BytesIO(element_png))
        return image
    except Exception as e:
        if DEBUG:
            print(f"要素のスクリーンショット取得エラー: {e}")
        return None

def create_enhanced_text_mask(image_array, text_color_rgb, threshold=50):
    """
    Create enhanced text mask to exclude text pixels
    
    Args:
        image_array: numpy array of the image
        text_color_rgb: Text color as (r, g, b) tuple
        threshold: Distance threshold for text detection
    
    Returns:
        boolean mask where True = text pixels
    """
    text_color = np.array(text_color_rgb)
    distances = np.linalg.norm(image_array - text_color, axis=2)
    return distances <= threshold

def calculate_true_background_luminance(image, text_color_rgb):
    """
    Calculate true background luminance using dominant clustering algorithm
    
    Args:
        image: PIL Image of the element
        text_color_rgb: Text color as (r, g, b) tuple
    
    Returns:
        tuple: (true_background_luminance, true_background_rgb)
    """
    if image is None:
        return None, None
    
    try:
        # Convert image to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Convert to numpy array
        image_array = np.array(image)
        h, w, c = image_array.shape
        
        # Step 1: Remove text pixels using enhanced mask
        text_mask = create_enhanced_text_mask(image_array, text_color_rgb, threshold=50)
        background_pixels = image_array[~text_mask].reshape(-1, 3)
        
        if len(background_pixels) < 10:
            # Fallback: use all pixels if insufficient background found
            background_pixels = image_array.reshape(-1, 3)
        
        # Step 2: Apply K-means clustering to group background pixels
        # Check for unique colors first to avoid convergence warnings
        unique_colors = np.unique(background_pixels.reshape(-1, background_pixels.shape[-1]), axis=0)
        n_unique = len(unique_colors)
        
        if n_unique <= 1:
            # Only one unique color - use it directly
            dominant_bg_color = unique_colors[0] if n_unique == 1 else np.mean(background_pixels, axis=0)
        else:
            # Use clustering with appropriate number of clusters
            n_clusters = min(4, n_unique, len(background_pixels))
            
            # Suppress convergence warnings for single color cases
            import warnings
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=UserWarning)
                kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
                clusters = kmeans.fit(background_pixels)
            
            # Step 3: Find the largest cluster (dominant background)
            labels_count = np.bincount(clusters.labels_)
            largest_cluster_idx = np.argmax(labels_count)
            dominant_bg_color = clusters.cluster_centers_[largest_cluster_idx]
        
        # Convert to integer RGB tuple
        true_bg_rgb = tuple(int(x) for x in dominant_bg_color)
        
        # Calculate luminance of dominant background color
        text_r_linear = srgb_to_linear(true_bg_rgb[0])
        text_g_linear = srgb_to_linear(true_bg_rgb[1])
        text_b_linear = srgb_to_linear(true_bg_rgb[2])
        true_bg_luminance = linear_rgb_to_luminance(text_r_linear, text_g_linear, text_b_linear)
        
        return true_bg_luminance, true_bg_rgb
        
    except Exception as e:
        if DEBUG:
            print(f"真背景色計算エラー (Dominant Clustering): {e}")
        return None, None

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

def calculate_improved_contrast_ratio(foreground_color, true_bg_luminance):
    """
    Calculate contrast ratio using true background luminance
    """
    if true_bg_luminance is None:
        return None
    
    fg_luminance = rgb_to_luminance(foreground_color)
    
    # Ensure L1 is the lighter color
    l1 = max(fg_luminance, true_bg_luminance)
    l2 = min(fg_luminance, true_bg_luminance)
    
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
            
            # Calculate original contrast ratio
            contrast_ratio = calculate_contrast_ratio(element['color'], element['backgroundColor'])
            
            # Try to get the actual DOM element for screenshot analysis
            true_bg_luminance = None
            true_bg_rgb = None
            improved_contrast_ratio = None
            element_image = None

            try:
                # Find the element using XPath
                dom_element = driver.find_element(By.XPATH, element['xpath'])
                
                # Capture element screenshot
                element_image = capture_element_screenshot(driver, dom_element)
                
                if element_image:
                    # Parse text color
                    rgb_match = re.match(r'rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*[\d.]+)?\)', element['color'])
                    if rgb_match:
                        text_rgb = (int(rgb_match.group(1)), int(rgb_match.group(2)), int(rgb_match.group(3)))
                        
                        # Calculate true background luminance
                        true_bg_luminance, true_bg_rgb = calculate_true_background_luminance(element_image, text_rgb)
                        
                        if true_bg_luminance is not None:
                            # Calculate improved contrast ratio
                            improved_contrast_ratio = calculate_improved_contrast_ratio(element['color'], true_bg_luminance)
                            
                            if DEBUG:
                                print(f"  真背景色: rgb{true_bg_rgb}, 輝度: {true_bg_luminance:.4f}")
                                print(f"  改善されたコントラスト比: {improved_contrast_ratio:.2f}:1")
                    
            except Exception as e:
                if DEBUG:
                    print(f"  要素の詳細解析をスキップ: {e}")

            # スクリーンショット保存（オプション）
            if SAVE_SCREENSHOTS:
                try:
                    # 保存ディレクトリが存在しない場合は作成（初回のみ）
                    if i == 0:
                        os.makedirs(SCREENSHOT_DIR, exist_ok=True)

                    # element_imageが既に取得されている場合はそれを保存
                    if element_image is not None:
                        filename = os.path.join(SCREENSHOT_DIR, f"{i:04d}.png")
                        element_image.save(filename)
                    else:
                        # element_imageが取得されていない場合は、capture_element_screenshotを呼び出す
                        if 'dom_element' not in locals() or dom_element is None:
                            dom_element = driver.find_element(By.XPATH, element['xpath'])

                        screenshot_image = capture_element_screenshot(driver, dom_element)
                        if screenshot_image is not None:
                            filename = os.path.join(SCREENSHOT_DIR, f"{i:04d}.png")
                            screenshot_image.save(filename)

                except Exception as e:
                    if DEBUG:
                        print(f"  警告: 要素 {i} のスクリーンショット取得に失敗: {e}")

            # Use improved contrast ratio if available, otherwise use original
            final_contrast_ratio = improved_contrast_ratio if improved_contrast_ratio is not None else contrast_ratio
            
            # Determine WCAG compliance using final contrast ratio
            compliance = determine_wcag_compliance(element, final_contrast_ratio)
            
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
                'improved_contrast_ratio': round(improved_contrast_ratio, 2) if improved_contrast_ratio is not None else None,
                'true_background_luminance': round(true_bg_luminance, 4) if true_bg_luminance is not None else None,
                'true_background_rgb': true_bg_rgb,
                'final_contrast_ratio': round(final_contrast_ratio, 2),
                'compliance': compliance
            }
            
            results.append(result)
        
        # Create final report (use final_contrast_ratio for compliance determination)
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
                
                # Add true background color if available
                if element.get('true_background_rgb'):
                    true_bg_rgb = element['true_background_rgb']
                    print(f"  真背景色: rgb({true_bg_rgb[0]}, {true_bg_rgb[1]}, {true_bg_rgb[2]}) (輝度: {element['true_background_luminance']:.4f})")
                else:
                    print(f"  真背景色: 解析不可")
                
                print(f"  コントラスト比 (通常): {element['contrast_ratio']}:1")
                
                # Show improved contrast ratio if available
                if element.get('improved_contrast_ratio'):
                    print(f"  コントラスト比 (改善): {element['improved_contrast_ratio']}:1")
                    print(f"  最終コントラスト比: {element['final_contrast_ratio']}:1 (改善後)")
                else:
                    print(f"  最終コントラスト比: {element['final_contrast_ratio']}:1 (通常)")
                
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
            
            # True background analysis statistics
            analyzed_elements = len([e for e in results['compliant_list'] + results['non_compliant_list'] if e.get('true_background_rgb')])
            print(f"真背景色解析成功: {analyzed_elements}個/{results['total_text_elements']}個")
            
            # Show improvement statistics for non-compliant elements
            improved_elements = len([e for e in results['non_compliant_list'] if e.get('improved_contrast_ratio') and e['improved_contrast_ratio'] != e['contrast_ratio']])
            if improved_elements > 0:
                print(f"改善されたコントラスト比を持つ要素: {improved_elements}個")

        # Export results to CSV
        csv_filename = export_to_csv(results, url)

    except Exception as e:
        print(f"エラー: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()