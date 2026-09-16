import argparse
import logging
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime

# Cấu hình Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# Đĩnh nghĩa cấu hình cho các loại hình
CATEGORY_CONFIG = {
    "Nhà hẻm": {
        "prop_filename": "alley_houses.csv",
        "amenity_filename": "alley_house.csv",
        "default_max_pages":10,
        "columns": [
            'Ma_BDS', 'Dia_chi', 'Tong_gia (trieu)', 'Tien_m2 (trieu/m2)', 'Loại hình',
            'Chiều ngang', 'Chiều dài', 'Hướng cửa chính', 'Số phòng ngủ', 'Số phòng tắm',
            'Số tầng', 'Diện tích đất công nhận', 'Diện tích sử dụng', 'Đường trước nhà',
            'Nội thất', 'Giấy tờ pháp lý'
        ]
    },
    "Căn hộ chung cư": {
        "prop_filename": "apartments.csv",
        "amenity_filename": "apartment.csv",
        "default_max_pages":10,        
        "columns": [
            'Ma_BDS', 'Dia_chi', 'Tong_gia (trieu)', 'Tien_m2 (trieu/m2)', 'Loại hình',
            'Địa chỉ chi tiết', 'Hướng ban công', 'Số phòng ngủ', 'Số phòng tắm',
            'Diện tích tim tường', 'Diện tích sử dụng', 'Nội thất', 'Tên dự án / tòa nhà',
            'Tình trạng sử dụng'
        ]
    },
    "Đất": {
        "prop_filename": "land.csv",
        "amenity_filename": "land.csv",
        "default_max_pages":10,
        "columns": [
            'Ma_BDS', 'Dia_chi', 'Tong_gia (trieu)', 'Tien_m2 (trieu/m2)', 'Loại hình',
            'Chiều ngang', 'Chiều dài', 'Hướng cửa chính'
        ]
    },
    "Nhà mặt tiền": {
        "prop_filename": "street_houses.csv",
        "amenity_filename": "street_houses.csv",
        "default_max_pages":10,
        "columns": [
            'Ma_BDS', 'Dia_chi', 'Tong_gia (trieu)', 'Tien_m2 (trieu/m2)', 'Loại hình',
            'Chiều ngang', 'Chiều dài', 'Hướng cửa chính', 'Số phòng ngủ', 'Số phòng tắm',
            'Số tầng', 'Diện tích đất công nhận', 'Diện tích sử dụng', 'Đường trước nhà',
            'Nội thất', 'Giấy tờ pháp lý'
        ]
    }
}

# 
def parse_price(price_str):
    """Parse a raw price string into a numeric value."""
    try:
        parts = price_str.strip().split()
        val = float(parts[0].replace(',', '.'))
        if parts[-1] == 'tỷ':
            return val * 1000000
        return val
    except (ValueError, IndexError):
        return None

def parse_price_m2(price_m2_str):
    """Parse price per square meter."""
    try:
        return float(price_m2_str.strip().split()[0].replace(',', '.'))
    except (ValueError, IndexError):
        return None

def parse_num_field(value_str):
    """Extract a numeric value from a string."""
    if not value_str:
        return None
    try:
        return float(value_str.split()[0])
    except (ValueError, IndexError):
        return None

def parse_amenities(soup_link, ma_bds):
    """Extract a list of nearby amenities."""
    amenities = []
    tien_ich_block = soup_link.find('div', class_="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3")
    if not tien_ich_block:
        return amenities

    for ti in tien_ich_block.find_all('div', class_="rounded-lg border border-gray-200 bg-white p-4"):
        col_name_tag = ti.find('h4', class_="text-base font-bold text-gray-800")
        if not col_name_tag:
            continue
        col_name = col_name_tag.text.replace('Gần', '').strip()

        for item in ti.find_all('div', class_="group/item flex items-baseline justify-between gap-2"):
            name_tag = item.find('span', class_="inline-block whitespace-nowrap text-xs text-gray-700 transition-transform duration-(--marquee-duration,1s) ease-linear group-hover/item:translate-x-(--marquee-offset,0px)")
            value_tag = item.find('span', class_="shrink-0 text-sm font-semibold text-primary")
            
            if not name_tag or not value_tag:
                continue

            value_str = value_tag.text.strip()
            try:
                if 'k' in value_str:
                    val = float(value_str.replace('km', '').strip()) * 1000
                else:
                    val = float(value_str.replace('m', '').strip())
            except ValueError:
                val = None

            amenities.append({
                'Ma_BDS': ma_bds,
                'Loai_tien_ich': col_name,
                'Ten_tien_ich': name_tag.text.strip(),
                'Khoảng cách': val
            })
    return amenities

def scrape_category(category_name, config, session, max_pages, run_timestamp, properties_dir, amenities_dir):
    """Scrape data for a specific real-estate property type."""
    type = {
        "Nhà hẻm":"alley",
        "Căn hộ chung cư": "apartment",
        "Đất": "land",
        "Nhà mặt tiền": "street"
    }
    type_name = type[category_name]
    logging.info(f"=== Starting data scraping: {type_name} (Total pages:: {max_pages}) ===")
    
    properties_data = []
    amenities_data = []
    total_bds = 0

    for page in range(1, max_pages + 1):
        url = f'https://moso.vn/tim-kiem-nha-dat?q=TP.HCM&trang={page}'
        logging.info(f"[{type_name}] Scraping page  {page}/{max_pages}")

        try:
            resp = session.get(url, timeout=10)
            resp.raise_for_status()
        except requests.RequestException as e:
            logging.error(f"Failed to connect to page {page}: {e}")
            continue

        soup = BeautifulSoup(resp.text, 'html.parser')
        cards = soup.find_all('article', class_="group relative hidden rounded-[12px] border border-gray-200 bg-white transition-all duration-200 hover:border-primary/30 hover:shadow-lg md:block")

        for card in cards:
            tag_type = card.find('span', class_="rounded-full bg-gray-100 px-3 text-xs font-medium leading-7 text-black")
            loai_dat = tag_type.text.strip() if tag_type else 'None'

            if loai_dat != category_name:
                continue

            total_bds += 1
            detail_link = 'https://moso.vn' + card.a['href']

            try:
                detail_resp = session.get(detail_link, timeout=10)
                detail_resp.raise_for_status()
            except requests.RequestException:
                continue

            soup_detail = BeautifulSoup(detail_resp.text, 'html.parser')
            thong_tin = soup_detail.find('div', class_="flex justify-between items-start gap-2 lg:gap-8 flex-wrap lg:flex-nowrap")

            if not thong_tin:
                continue

            dia_chi_tag = thong_tin.find('h2', class_="flex text-black text-lg md:text-2xl font-bold leading-8 -tracking-[0.36px]")
            tong_gia_tag = thong_tin.find('span', class_="text-3xl md:text-4xl font-extrabold text-primary")
            tien_m2_tag = thong_tin.find('span', class_="text-base md:text-lg font-semibold text-primary/85")
            ma_bds_tag = thong_tin.find('span', class_="text-sm sm:text-base font-bold text-black hover:text-primary cursor-pointer")

            if not all([dia_chi_tag, tong_gia_tag, tien_m2_tag, ma_bds_tag]):
                continue

            ma_bds = ma_bds_tag.text.strip()

            item_data = {
                'Ma_BDS': ma_bds,
                'Dia_chi': dia_chi_tag.text.strip(),
                'Tong_gia (trieu)': parse_price(tong_gia_tag.text),
                'Tien_m2 (trieu/m2)': parse_price_m2(tien_m2_tag.text),
                'Loại hình': loai_dat
            }

            dl_block = soup_detail.find('dl', class_="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3")
            if dl_block:
                for feat in dl_block.find_all('div', class_="flex flex-col gap-1 min-w-0"):
                    dt = feat.find('dt', class_="text-sm text-gray-600 leading-tight")
                    dd = feat.find('dd', class_="text-md font-bold leading-tight text-gray-900")
                    if dt and dd:
                        item_data[dt.text.strip()] = dd.text.strip()

            if category_name in ["Nhà hẻm", "Nhà mặt tiền", "Căn hộ chung cư"]:
                item_data['Số phòng ngủ'] = parse_num_field(item_data.get('Số phòng ngủ'))
                item_data['Số phòng tắm'] = parse_num_field(item_data.get('Số phòng tắm'))

            if category_name in ["Nhà hẻm", "Nhà mặt tiền"]:
                item_data['Số tầng'] = parse_num_field(item_data.get('Số tầng'))

            row = {col: item_data.get(col, None) for col in config["columns"]}
            properties_data.append(row)

            amenities_data.extend(parse_amenities(soup_detail, ma_bds))

    if properties_data:
        df_prop = pd.DataFrame(properties_data)
        # Thêm timestamp vào tên file
        new_prop_name = config["prop_filename"].replace(".csv", f"_{run_timestamp}.csv")
        out_prop_path = properties_dir / new_prop_name
        df_prop.to_csv(out_prop_path, index=False, encoding='utf-8-sig')
        logging.info(f"Saved {len(df_prop)} properties to: {out_prop_path}")

    # Lưu kết quả Amenities
    if amenities_data:
        df_amen = pd.DataFrame(amenities_data)
        # Thêm timestamp vào tên file
        new_amen_name = config["amenity_filename"].replace(".csv", f"_{run_timestamp}.csv")
        out_amen_path = amenities_dir / new_amen_name
        df_amen.to_csv(out_amen_path, index=False, encoding='utf-8-sig')
        logging.info(f"Saved {len(df_amen)} amenities to: {out_amen_path}")

    logging.info(f"Completed {type_name}! Collected a total of {total_bds} properties.\n")

def main():
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    parser = argparse.ArgumentParser(description="Automatic script for crawling real-estate data from Moso.")
    
    parser.add_argument(
        "--category", "-c",
        type=str, 
        choices=["alley", "apartment", "land", "street", "all"], 
        default="all", 
        help="Select the property type to scrape: alley (Alley House), apartment (Apartment), land (Land), street (Street-front House), all (All)."
    )
    
    parser.add_argument(
        "--pages", "-p",
        type=int,
        default=None,
        help="Maximum number of pages to scrape (default: all pages)."
    )

    # Đã cập nhật default thành "data"
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="data",
        help="Root directory for storing data (default: 'data' in the working directory)"
    )
    
    args = parser.parse_args()

    base_out_dir = Path(args.output).resolve()
    properties_dir = base_out_dir / "properties"
    amenities_dir = base_out_dir / "amenities"

    # Khởi tạo thư mục nếu chưa tồn tại
    properties_dir.mkdir(parents=True, exist_ok=True)
    amenities_dir.mkdir(parents=True, exist_ok=True)

    cat_mapping = {
        "alley": ["Nhà hẻm"],
        "apartment": ["Căn hộ chung cư"],
        "land": ["Đất"],
        "street": ["Nhà mặt tiền"],
        "all": list(CATEGORY_CONFIG.keys())
    }

    targets = cat_mapping[args.category]
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })

    for cat in targets:
        max_pages = args.pages if args.pages is not None else CATEGORY_CONFIG[cat]["default_max_pages"]
        # Gọi hàm truyền thêm timestamp và các thư mục động
        scrape_category(cat, CATEGORY_CONFIG[cat], session, max_pages, run_timestamp, properties_dir, amenities_dir)

if __name__ == "__main__":
    main()