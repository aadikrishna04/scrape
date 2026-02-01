import requests
import pandas as pd
from typing import List, Dict, Optional

HEADERS = {
    "referer": "https://www.nasdaq.com/",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "accept": "application/json, text/plain, */*"
}

def getEarningsByDate(date: str, page: Optional[int] = 1, page_size: Optional[int] = 50) -> List[Dict]:
    """
    Retrieve all companies that posted earnings on a specific date.

    :param date: The date for which to retrieve earnings reports, formatted as YYYY-MM-DD.
    :param page: The page number for paginated results.
    :param page_size: The number of results per page.
    :return: A list of companies with their earnings report details.
    """
    url = "https://api.nasdaq.com/api/calendar/earnings"
    params = {
        "date": date
    }

    response = requests.get(url, headers=HEADERS, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    # Extract data using the specified data path
    earnings_data = data.get("data", {}).get("rows", [])

    # Map fields to match actual API response (data.rows items)
    results = []
    for item in earnings_data:
        results.append({
            "symbol": item.get("symbol"),
            "name": item.get("name"),
            "time": item.get("time"),
            "eps": item.get("eps"),
            "surprise": item.get("surprise"),
            "market_cap": item.get("marketCap"),
            "fiscal_quarter_ending": item.get("fiscalQuarterEnding"),
            "eps_forecast": item.get("epsForecast"),
            "no_of_ests": item.get("noOfEsts"),
        })

    # Implement pagination logic if necessary (not shown in the endpoint analysis)
    # For now, we assume all data is returned in a single response

    return results

results = getEarningsByDate("2026-01-28")
df = pd.DataFrame(results)
pd.set_option("display.max_columns", None)
pd.set_option("display.width", None)
pd.set_option("display.max_colwidth", 40)
print(df.to_string(index=False))