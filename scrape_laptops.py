from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import pandas as pd
import time
import re
import math
import random 
import os 

# --- Configuration ---
chrome_driver_path = "chromedriver.exe" 
laptop_models_csv = "laptop_models.csv" 
output_csv_name = "scraped_laptop_data_amazon.csv" 

column_order = ['Model', 'Brand', 'Price', 'Rating', 'Graphics Card', 'Memory', 'Processor', 'Type: Work or Gaming']

def extract_simple_brand(text):
    text_lower = text.lower()
    brands = [
        'hp', 'lenovo', 'dell', 'asus', 'acer', 'msi', 'apple', 'samsung', 
        'microsoft', 'lg', 'gigabyte', 'razer', 'alienware', 'xiaomi', 'tecno', 
        'zebronics', 'microsoft surface', 'huawei', 'vaio', 'toshiba', 'fujitsu'
    ]
    for brand in brands:
        if brand in text_lower:
            if brand == 'microsoft surface':
                return 'Microsoft Surface'
            if re.search(r'\b' + re.escape(brand) + r'\b', text_lower):
                return brand.capitalize() 
    return None 


def calculate_relevance_score(search_result_title, original_model_name):
    original_words = set(re.findall(r'\b\w+\b', original_model_name.lower()))
    result_words = set(re.findall(r'\b\w+\b', search_result_title.lower()))

    stopwords = {'a', 'an', 'the', 'and', 'or', 'for', 'with', 'from', 'in', 'on', 'of'} 
    original_words = {word for word in original_words if word not in stopwords and len(word) > 1}
    result_words = {word for word in result_words if word not in stopwords and len(word) > 1} 

    common_words = original_words.intersection(result_words)
    score = len(common_words)

    original_brand = extract_simple_brand(original_model_name)
    result_brand = extract_simple_brand(search_result_title)

    if original_brand and result_brand:
        if original_brand == result_brand:
            score += 15 # Even higher bonus if brands exactly match
        else:
            score -= 30 # Even more severe penalty if brands mismatch
    elif original_brand and not result_brand:
        score -= 5 
    model_parts_to_match = []
    # Try to extract actual model number/series
    model_match = re.search(r'\b(?:victus|ideapad|thinkpad|zenbook|vivobook|legion|omen|spectre|inspiron|pavilion|macbook|galaxy book)\s*([\w\d\-\.]+)', original_model_name.lower())
    if model_match:
        model_parts_to_match = model_match.group(0).split() + model_match.group(1).split('-')
        model_parts_to_match = [p for p in model_parts_to_match if len(p) > 2] # Only meaningful parts
    
    for part in model_parts_to_match:
        if part in result_words:
            score += 3 # Bonus for matching specific model parts

    if original_model_name.lower() in search_result_title.lower(): # Check full phrase match
        score += 5 # Added bonus for full name match.
        
    if "refurbished" in search_result_title.lower() or "renewed" in search_result_title.lower():
        score -= 50 # Extremely severe penalty to filter out refurbished/renewed

    return score


# --- 1. Load your CSV file ---
print(f"Loading laptop models from {laptop_models_csv}...")
try:
    df_models = pd.read_csv(laptop_models_csv)
    if 'Model' in df_models.columns:
        laptop_models = df_models['Model'].tolist()
        
        
        print(f"Successfully loaded {len(df_models.index)} laptop models for processing.")
        print("First 5 models:", laptop_models[:5])
    else:
        print(f"Error: Column 'Model' not found in {laptop_models_csv}.")
        print("Please ensure your CSV has a column exactly named 'Model'.")
        exit()
except FileNotFoundError:
    print(f"Error: '{laptop_models_csv}' not found.")
    print("Please make sure the CSV file is in the same folder as this script.")
    exit()
except Exception as e:
    print(f"An error occurred while reading the CSV: {e}")
    exit()

# --- 2. Initialize the WebDriver ---
chrome_options = Options()
chrome_options.add_argument("--headless") 
chrome_options.add_argument("--disable-gpu") 
chrome_options.add_argument("--no-sandbox") 
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36")

driver = None
scraped_data_in_memory = [] 

csv_header_written = False
if os.path.exists(output_csv_name):
    csv_header_written = True 
    print(f"Warning: '{output_csv_name}' already exists. Appending to it.")
else:
    print(f"Creating new file: '{output_csv_name}'")


try:
    print("\nAttempting to open Chrome browser...")
    service = Service(executable_path=chrome_driver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    print("Chrome browser opened successfully!")

    # --- 3. Loop through each laptop model for scraping ---
    for i, model_name in enumerate(laptop_models):
        print(f"\n--- Scraping data for Model {i+1}/{len(laptop_models)}: {model_name} ---")

        # Define default values for each field for the current model
        brand = 'N/A'
        price = 'N/A'
        rating = 'N/A'
        graphics_card = 'N/A'
        memory = 'N/A'
        processor = 'N/A'
        
        if "gaming" in model_name.lower():
            type_work_gaming = "Gaming"
        else:
            type_work_gaming = "Work"

        try:
            search_query = model_name.replace(' ', '+')
            amazon_search_url = f"https://www.amazon.in/s?k={search_query}"
            driver.get(amazon_search_url)

            # --- Wait for search results and implement relevance check ---
            best_match_link = None
            best_match_title = "" 
            max_score = -100 # Very low initial score to handle severe penalties

            try:
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-component-type="s-search-result"]'))
                )
                time.sleep(random.uniform(7, 12)) 
                print("  Amazon search results page loaded. Checking relevance...")

                product_cards = driver.find_elements(By.CSS_SELECTOR, 'div[data-component-type="s-search-result"]')
                
                if not product_cards:
                    print(f"  No product cards found on search results page for '{model_name}'.")
                
                for j, card in enumerate(product_cards[:15]): # Check up to first 15 results
                    result_title = ""
                    result_link = None
                    is_sponsored = False

                    try:
                        title_h2_element = card.find_element(By.CSS_SELECTOR, 'h2.a-text-normal')
                        result_title = title_h2_element.text.strip()
                        
                        if title_h2_element.get_attribute('aria-label') and "sponsored ad" in title_h2_element.get_attribute('aria-label').lower():
                            is_sponsored = True
                            
                        all_links_in_card = card.find_elements(By.TAG_NAME, 'a')
                        for link_el in all_links_in_card:
                            href = link_el.get_attribute('href')
                            if href and '/dp/' in href and not ('/s?' in href or 'node=' in href or '/gp/' in href):
                                result_link = href
                                break

                        if not result_link:
                            # print(f"      Result {j+1}: No valid product detail link found. Skipping.") 
                            continue

                        # Debugging print statements (commented out for clean output during full run)
                        # print(f"      Debugging: Original Model: '{model_name[:50]}...'")
                        # print(f"      Debugging: Result Title: '{result_title[:70]}...'")

                        current_score = calculate_relevance_score(result_title, model_name)
                        
                        if is_sponsored:
                            current_score -= 10 # Penalize sponsored ads

                        # print(f"    Result {j+1}: '{result_title[:70]}...' (Score: {current_score}) {'(Sponsored)' if is_sponsored else ''}") 

                        if current_score > max_score:
                            max_score = current_score
                            best_match_link = result_link
                            best_match_title = result_title 

                    except NoSuchElementException:
                        # print(f"      Result {j+1}: Card structure not as expected. Skipping.") 
                        continue 
                    except Exception as e:
                        print(f"      Error processing search result card {j+1} completely: {e}")

                # Decide if a good enough match was found (UPDATED: Stricter threshold)
                if best_match_link and max_score >= 8: # Higher score threshold for navigating to product page
                    product_link = best_match_link
                    print(f"  Best relevant product found (Score: {max_score}). Navigating to: {product_link}")
                else:
                    print(f"  No sufficiently relevant product found for '{model_name}' (Best Score: {max_score}). Moving to next.")
                    laptop_data_to_save = { 
                        'Model': model_name, 'Brand': brand, 'Price': price, 'Rating': rating, 'Graphics Card': graphics_card,
                        'Memory': memory, 'Processor': processor, 'Type: Work or Gaming': type_work_gaming
                    }
                    scraped_data_in_memory.append(laptop_data_to_save)
                    df_single_laptop = pd.DataFrame([laptop_data_to_save])
                    df_single_laptop = df_single_laptop[column_order]
                    if not csv_header_written:
                        df_single_laptop.to_csv(output_csv_name, mode='a', header=True, index=False)
                        csv_header_written = True
                    else:
                        df_single_laptop.to_csv(output_csv_name, mode='a', header=False, index=False)
                    print(f"  Data for '{model_name[:50]}...' saved to CSV live (as N/A).")
                    time.sleep(random.uniform(10, 15)) 
                    continue

            except TimeoutException:
                print(f"  Timed out waiting for Amazon search results for '{model_name}'. No results or slow load. Moving to next.")
                laptop_data_to_save = { 
                    'Model': model_name, 'Brand': brand, 'Price': price, 'Rating': rating, 'Graphics Card': graphics_card,
                    'Memory': memory, 'Processor': processor, 'Type: Work or Gaming': type_work_gaming
                }
                scraped_data_in_memory.append(laptop_data_to_save)
                df_single_laptop = pd.DataFrame([laptop_data_to_save])
                df_single_laptop = df_single_laptop[column_order]
                if not csv_header_written:
                    df_single_laptop.to_csv(output_csv_name, mode='a', header=True, index=False)
                    csv_header_written = True
                else:
                    df_single_laptop.to_csv(output_csv_name, mode='a', header=False, index=False)
                print(f"  Data for '{model_name[:50]}...' saved to CSV live (as N/A).")
                time.sleep(random.uniform(10, 15)) 
                continue

            # --- Navigate to the product detail page ---
            driver.get(product_link)

            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.ID, 'productTitle'))
            )
            time.sleep(random.uniform(7, 12)) 
            print("  Product detail page loaded.")

            # --- Extract Price ---
            price = 'N/A'
            try:
                price_element_offscreen = driver.find_element(By.CSS_SELECTOR, 'span.a-offscreen')
                price = price_element_offscreen.get_attribute('textContent').strip()
                print(f"    Price (offscreen): {price}")
            except NoSuchElementException:
                try:
                    price_container_selector = '#corePrice_feature_div, #priceblock_ourprice, .reinventPricePriceToPayMargin'
                    price_container = driver.find_element(By.CSS_SELECTOR, price_container_selector)

                    price_whole = price_container.find_element(By.CSS_SELECTOR, 'span.a-price-whole').text.strip()
                    
                    try:
                        price_fraction = price_container.find_element(By.CSS_SELECTOR, 'span.a-price-fraction').text.strip()
                        price = f"₹{price_whole}.{price_fraction}"
                    except NoSuchElementException:
                        pass
                    print(f"    Price (visible): {price}")
                except NoSuchElementException:
                    print("    Price not found on product page via common visible selectors.")
            except Exception as e:
                print(f"    Error extracting price: {e}")

            rating = 'N/A'
            try:
                rating_text = ""
                try: 
                    rating_summary_element = driver.find_element(By.CSS_SELECTOR, '#averageCustomerReviews span.a-icon-alt')
                    rating_text = rating_summary_element.get_attribute('innerHTML').strip()
                except NoSuchElementException:
                    try: 
                        review_link_element = driver.find_element(By.CSS_SELECTOR, '#acrCustomerReviewLink')
                        aria_label_rating = review_link_element.get_attribute('aria-label')
                        if aria_label_rating and "out of" in aria_label_rating.lower():
                            rating_text = aria_label_rating
                    except NoSuchElementException:
                        try: 
                            general_rating_element = driver.find_element(By.CSS_SELECTOR, 'span.a-icon-alt')
                            
                            if "previous" not in general_rating_element.get_attribute('innerHTML').lower():
                                rating_text = general_rating_element.get_attribute('innerHTML').strip()
                        except NoSuchElementException:
                            pass 

                if rating_text:
                    rating_match = re.search(r'(\d+\.?\d*)', rating_text) 
                    if rating_match:
                        rating = rating_match.group(1)
                        # if "out of 5 stars" not in rating_text.lower(): # Debug print commented out
                        # print(f"    Warning: Rating text ('{rating_text}') found, but missing 'out of 5 stars'. Using numerical part only.")
                    else:
                        # print(f"    Rating text found ('{rating_text}') but no numerical rating extracted. Setting to N/A.") # Debug print commented out
                        rating = 'N/A' 
                else:
                    # print("    No rating text found. Setting to N/A.") # Debug print commented out
                    rating = 'N/A'
                
                print(f"    Rating: {rating}")
            except Exception as e:
                print(f"    Error extracting rating: {e}")

            # --- Extracting detailed specs (Graphics Card, Memory, Processor, Brand) ---
            specs_dict = {}
            full_description_for_inference = "" 

            try:
                specs_table = None
                try: 
                    specs_table = driver.find_element(By.CSS_SELECTOR, '#productDetails_techSpec_section_1 table.a-normal.a-spacing-micro')
                except NoSuchElementException:
                    try:
                        specs_table = driver.find_element(By.CSS_SELECTOR, 'table.a-normal.a-spacing-micro')
                    except NoSuchElementException:
                        pass 

                if specs_table:
                    table_rows = specs_table.find_elements(By.TAG_NAME, 'tr')
                    for row in table_rows:
                        try:
                            label_element = row.find_element(By.CSS_SELECTOR, 'td:nth-child(1) span.a-text-bold')
                            value_element = row.find_element(By.CSS_SELECTOR, 'td:nth-child(2) span.a-size-base.po-break-word')
                            label = label_element.text.strip().replace(':', '').strip()
                            value = value_element.text.strip()
                            specs_dict[label] = value
                        except NoSuchElementException:
                            pass
                        except Exception as e:
                            print(f"      Error parsing table row: {e}")
                    # print(f"    Extracted structured specs (from table): {specs_dict}") 

                if not specs_dict:
                    try:
                        detail_bullets_ul = driver.find_element(By.CSS_SELECTOR, '#detailBullets_feature_div ul.a-unordered-list')
                        list_items = detail_bullets_ul.find_elements(By.TAG_NAME, 'li')

                        for item in list_items:
                            try:
                                label_element = item.find_element(By.CSS_SELECTOR, 'span.a-text-bold')
                                label = label_element.text.strip().replace(':', '').strip()

                                item_text_full = item.text.strip()
                                value = item_text_full.replace(label_element.text.strip(), '', 1).strip()

                                specs_dict[label] = value
                            except NoSuchElementException:
                                pass
                            except Exception as e:
                                print(f"      Error parsing specific list item: {e}")
                        # print(f"    Extracted structured specs (from UL list): {specs_dict}") 
                    except NoSuchElementException:
                        print("    Neither table nor UL specs container found. Specs will be N/A.")
                    except Exception as e:
                        print(f"    Error processing structured UL specs: {e}.")
                
                # --- After trying both methods, populate variables from specs_dict ---

                # Extract Brand
                brand_from_specs = specs_dict.get("Brand", None) 
                if brand_from_specs:
                    extracted_brand = extract_simple_brand(brand_from_specs)
                    if extracted_brand:
                        brand = extracted_brand
                    else: 
                        brand = brand_from_specs # Use raw if simple_brand couldn't extract
                
                if brand == 'N/A' or brand is None:
                    try:
                        brand_element_text = ""
                        try:
                            brand_element = driver.find_element(By.ID, 'bylineInfo')
                            brand_element_text = brand_element.text.strip()
                        except NoSuchElementException:
                            product_title_element = driver.find_element(By.ID, 'productTitle')
                            brand_element_text = product_title_element.text.strip()

                        extracted_brand_fallback = extract_simple_brand(brand_element_text)
                        if extracted_brand_fallback:
                            brand = extracted_brand_fallback
                        else:
                            first_word_match = re.match(r'^[A-Za-z]+', brand_element_text)
                            if first_word_match:
                                brand = first_word_match.group(0)
                    except Exception as e:
                        print(f"    Error extracting brand (fallback): {e}")

                # Processor (UPDATED for better specificity)
                processor_text = specs_dict.get("Processor", "").lower()
                if not processor_text:
                    processor_text = specs_dict.get("CPU Model", "").lower()
                if not processor_text and best_match_title: # Try best_match_title as source if specs_dict fails
                    processor_text = best_match_title.lower()
                
                # Regex for more specific processor models
                ryzen_match = re.search(r'(amd ryzen\s*[\d.x]+[hshx]?(?: \w+)?|amd ryzen\s*[3579]\s*\d*[hshx]?)', processor_text)
                intel_match = re.search(r'(intel core\s*i[3579]\s*\d*[ghx]?)', processor_text)
                apple_m_match = re.search(r'(apple m[1-3](?: pro| max| ultra)?)', processor_text)

                if ryzen_match: processor = ryzen_match.group(1).upper()
                elif intel_match: processor = intel_match.group(1).upper()
                elif apple_m_match: processor = apple_m_match.group(1).upper()
                elif processor_text: # Fallback to original text if no specific regex match but text exists
                    processor = specs_dict.get("Processor", specs_dict.get("CPU Model", 'N/A'))
                    if processor == 'N/A' and best_match_title: # If still N/A, try rough from title
                         processor = "INTEL CORE" if "intel core" in best_match_title.lower() else ("AMD RYZEN" if "amd ryzen" in best_match_title.lower() else "N/A")


                # Memory (RAM)
                memory_text = specs_dict.get("RAM", "").lower()
                if not memory_text:
                    memory_text = specs_dict.get("Memory", "").lower()
                if not memory_text: 
                    memory_text = specs_dict.get("RAM Memory Installed Size", "").lower() 
                ram_match = re.search(r'(\d+)\s*gb\s*ram', memory_text)
                if ram_match: memory = ram_match.group(1) + "GB"
                elif memory_text:
                    memory = specs_dict.get("RAM", specs_dict.get("Memory", specs_dict.get("RAM Memory Installed Size", 'N/A')))


                # Graphics Card (UPDATED for better specificity from title)
                graphics_text = specs_dict.get("Graphics Coprocessor", "").lower()
                if not graphics_text:
                    graphics_text = specs_dict.get("Graphics Card Description", "").lower()
                if not graphics_text:
                    graphics_text = specs_dict.get("GPU", "").lower()

                if not graphics_text and best_match_title: # Use best_match_title for graphics if specs_dict didn't yield
                    graphics_text = best_match_title.lower()
                
                # Regex for specific GPU models
                rtx_match = re.search(r'(nvidia rtx\s*\d{3,4}0)', graphics_text)
                gtx_match = re.search(r'(nvidia gtx\s*\d{3,4}0)', graphics_text)
                radeon_match = re.search(r'(amd radeon\s*(?:rx\s*\d{3,4}|vega|graphics)?)', graphics_text)

                if rtx_match: graphics_card = rtx_match.group(1).upper()
                elif gtx_match: graphics_card = gtx_match.group(1).upper()
                elif radeon_match: graphics_card = radeon_match.group(1).upper()
                elif "intel iris xe" in graphics_text: graphics_card = "Intel Iris Xe"
                elif "integrated graphics" in graphics_text or "intel uhd" in graphics_text or "intel hd" in graphics_text:
                    graphics_card = "Integrated"
                elif graphics_text: # Fallback to original value if no specific match
                    graphics_card = specs_dict.get("Graphics Coprocessor", specs_dict.get("Graphics Card Description", specs_dict.get("GPU", 'N/A')))
                    if graphics_card == 'N/A' and best_match_title: # If still N/A, use very rough from title
                        graphics_card = "Dedicated" if "rtx" in best_match_title.lower() or "gtx" in best_match_title.lower() or "radeon" in best_match_title.lower() else "Integrated"
                
                full_description_for_inference = " ".join(list(specs_dict.keys()) + list(specs_dict.values())).lower()


            except Exception as e:
                print(f"    Error processing structured specs: {e}. Specs will be N/A.")
                try:
                    full_description_for_inference = driver.find_element(By.TAG_NAME, 'body').text.lower()
                except:
                    pass

            except NoSuchElementException:
                print(f"  No valid product link found for '{model_name}' on Amazon search results page. Moving to next.")
            except TimeoutException:
                print(f"  Timed out loading product detail page for '{model_name}'. Moving to next.")
            except Exception as e:
                print(f"  An error occurred during product page navigation or extraction for '{model_name}': {e}")

        except Exception as e:
            print(f"An unexpected error occurred while processing '{model_name}': {e}")

        laptop_data_to_save = {
            'Model': model_name,
            'Brand': brand,
            'Price': price,
            'Rating': rating,
            'Graphics Card': graphics_card,
            'Memory': memory,
            'Processor': processor,
            'Type: Work or Gaming': type_work_gaming
        }
        scraped_data_in_memory.append(laptop_data_to_save) 

        df_single_laptop = pd.DataFrame([laptop_data_to_save])
        df_single_laptop = df_single_laptop[column_order]
        
        if not csv_header_written:
            df_single_laptop.to_csv(output_csv_name, mode='a', header=True, index=False)
            csv_header_written = True
        else:
            df_single_laptop.to_csv(output_csv_name, mode='a', header=False, index=False)
        
        print(f"  Data for '{model_name[:50]}...' saved to CSV live.")

        time.sleep(random.uniform(7, 15))

except Exception as e:
    print(f"\nAn error occurred during the scraping process: {e}")
    print("Ensure all configurations (ChromeDriver path, CSV name) are correct and check your internet connection.")
finally:
    if driver:
        driver.quit()
        print("\nBrowser closed.")

print(f"\nScraping process finished. Check '{output_csv_name}' for live updates.")