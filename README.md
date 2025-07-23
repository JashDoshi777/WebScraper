This project is a Python-based laptop specification scraper built using Selenium and Chrome WebDriver. It is designed to automate the process of collecting detailed specifications for laptops listed on Amazon based on a given list of model names. The tool reads model names from a CSV file, performs an automated search for each on Amazon, and extracts key technical details from the most relevant product listing.

The extracted information includes attributes such as brand, processor, RAM size, graphics card, operating system, screen size, rating, and price. These details are parsed and stored in a structured format and written to a CSV output file for easy access and further analysis.

The scraper simulates user behavior by launching a headless Chrome browser session using ChromeDriver, navigating Amazon’s interface, clicking on relevant links, and scraping data directly from the product detail pages. The script also includes logic to match product titles with the original model names to ensure accuracy and avoid mismatches.

This tool is especially useful for aggregating market data, performing product comparisons, building recommendation systems, or maintaining a product database. The scraper can be extended to include additional e-commerce platforms, implement fuzzy matching for better model alignment, or integrate with cloud storage for live data ingestion.

Proper handling of browser automation, wait times, and dynamic page elements has been considered to ensure robustness. The project demonstrates practical web scraping, data cleaning, and automation techniques suitable for real-world applications involving product intelligence.
