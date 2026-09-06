import requests
from bs4 import BeautifulSoup
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

data_dir = BASE_DIR / "Data"

path_csv = data_dir / "data_nhahem.csv"
path_csv_tien_ich = data_dir / "data_tien_ich_nhahem.csv"

# Khởi tạo Session ở ngoài cùng để tận dụng connection pooling giúp request nhanh hơn
session = requests.Session()

dct = {
    'Ma_BDS': [],
    'Dia_chi': [],
    'Tong_gia (trieu)': [],
    'Tien_m2 (trieu/m2)': [],
    'Loại hình': [],
    'Chiều ngang': [],
    'Chiều dài': [],
    'Hướng cửa chính': [],
    'Số phòng ngủ': [], 
    'Số phòng tắm': [], 
    'Số tầng': [], 
    'Diện tích đất công nhận': [], 
    'Diện tích sử dụng': [], 
    'Đường trước nhà': [],
    'Nội thất': [],
    'Giấy tờ pháp lý': []
}
dctt = {}
total_bds = 0 

for num in range(1, 779):
    url = f'https://moso.vn/tim-kiem-nha-dat?q=TP.HCM&trang={num}'
    print(f"Đang cào trang: {num}")
    
    try:
        html = session.get(url).text
    except requests.RequestException as e:
        print(f"Lỗi kết nối ở trang {num}: {e}")
        continue

    soup = BeautifulSoup(html, 'html.parser')
    result = soup.find_all('article', class_="group relative hidden rounded-[12px] border border-gray-200 bg-white transition-all duration-200 hover:border-primary/30 hover:shadow-lg md:block")
    
    for res in result:
        Loai_dat_tag = res.find('span', class_="rounded-full bg-gray-100 px-3 text-xs font-medium leading-7 text-black")
        Loai_dat = Loai_dat_tag.text if Loai_dat_tag else 'None'

        if Loai_dat.strip() != 'Nhà hẻm':
            continue 
            
        total_bds += 1
        link = 'https://moso.vn' + res.a['href']

        try:
            html_link = session.get(link).text
        except requests.RequestException:
            continue

        soup_link = BeautifulSoup(html_link, 'html.parser')
        Thong_tin = soup_link.find('div', class_="flex justify-between items-start gap-2 lg:gap-8 flex-wrap lg:flex-nowrap")

        # CHECK 1: Nếu không có khối Thông_tin, bỏ qua bài đăng này
        if not Thong_tin:
            continue

        # Trích xuất an toàn bằng cách dùng thẻ trung gian
        Dia_chi_tag = Thong_tin.find('h2', class_="flex text-black text-lg md:text-2xl font-bold leading-8 -tracking-[0.36px]")
        Tong_gia_tag = Thong_tin.find('span', class_="text-3xl md:text-4xl font-extrabold text-primary")
        Tien_m_2_tag = Thong_tin.find('span', class_="text-base md:text-lg font-semibold text-primary/85")
        Ma_BDS_tag = Thong_tin.find('span', class_="text-sm sm:text-base font-bold text-black hover:text-primary cursor-pointer")
        
        # CHECK 2: Phải có đủ 4 trường quan trọng mới xử lý tiếp
        if not all([Dia_chi_tag, Tong_gia_tag, Tien_m_2_tag, Ma_BDS_tag]):
            continue

        Dia_chi = Dia_chi_tag.text.strip()
        Tong_gia_str = Tong_gia_tag.text.strip()
        Tien_m_2_str = Tien_m_2_tag.text.strip()
        Ma_BDS = Ma_BDS_tag.text.strip()

        # Xử lý logic tính tiền
        try:
            if Tong_gia_str.split()[-1] == 'tỷ':
                Tong_gia = float(Tong_gia_str.split()[0].replace(',', '.')) * 1000000
            else:
                Tong_gia = float(Tong_gia_str.split()[0].replace(',', '.'))

            Tien_m_2 = float(Tien_m_2_str.split()[0].replace(',', '.'))
        except (ValueError, IndexError):
            # Nếu chuỗi giá trị bị sai định dạng (ví dụ: "Thỏa thuận"), gán là None
            Tong_gia = None
            Tien_m_2 = None

        dct_ = {
            'Ma_BDS': None,
            'Dia_chi': None,
            'Tong_gia (trieu)': None,
            'Tien_m2 (trieu/m2)': None,
            'Loại hình': None,
        }
        # Đẩy dữ liệu vào dictionary (chỉ đẩy khi đã qua hết các bước check lỗi)

        dct_.update({
            'Ma_BDS': Ma_BDS,
            'Dia_chi': Dia_chi,
            'Tong_gia (trieu)': Tong_gia,
            'Tien_m2 (trieu/m2)': Tien_m_2,
            'Loại hình': Loai_dat
        })

        # Trích xuất các thông tin bổ sung
        Thong_tin_bo_sung = soup_link.find('dl', class_="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3")

        # CHECK: Phải đảm bảo thẻ <dl> tồn tại thì mới tìm kiếm bên trong
        if Thong_tin_bo_sung:
            features = Thong_tin_bo_sung.find_all('div', class_="flex flex-col gap-1 min-w-0") 

            for feature in features:
                try:
                    feature_name_tag = feature.find('dt', class_="text-sm text-gray-600 leading-tight")
                    feature_value_tag = feature.find('dd', class_="text-md font-bold leading-tight text-gray-900")
                    
                    # Chỉ lấy text khi cả key (dt) và value (dd) đều tồn tại
                    if feature_name_tag and feature_value_tag:
                        feature_name = feature_name_tag.text.strip()
                        feature_value = feature_value_tag.text.strip()
                        # Cập nhật vào dictionary tạm
                        dct_[feature_name] = feature_value
                except Exception as e:
                    # Bỏ qua lỗi của từng feature nhỏ để không làm sập cả vòng lặp
                    # print(f"Lỗi khi trích xuất một thuộc tính bổ sung: {e}")
                    continue

        dct.setdefault('Ma_BDS', []).append(dct_['Ma_BDS'])
        dct.setdefault('Dia_chi', []).append(dct_['Dia_chi'])
        dct.setdefault('Tong_gia (trieu)', []).append(dct_['Tong_gia (trieu)'])
        dct.setdefault('Tien_m2 (trieu/m2)', []).append(dct_['Tien_m2 (trieu/m2)'])
        dct.setdefault('Loại hình', []).append(dct_['Loại hình'])
        dct.setdefault('Chiều ngang', []).append(dct_.get('Chiều ngang', None))
        dct.setdefault('Chiều dài', []).append(dct_.get('Chiều dài', None))
        dct.setdefault('Hướng cửa chính', []).append(dct_.get('Hướng cửa chính', None))
        dct.setdefault('Số phòng ngủ', []).append(float(dct_.get('Số phòng ngủ', None).split()[0]) if dct_.get('Số phòng ngủ', None) else None)
        dct.setdefault('Số phòng tắm', []).append(float(dct_.get('Số phòng tắm', None).split()[0]) if dct_.get('Số phòng tắm', None) else None)
        dct.setdefault('Số tầng', []).append(float(dct_.get('Số tầng', None).split()[0]) if dct_.get('Số tầng', None) else None)
        dct.setdefault('Diện tích đất công nhận', []).append(dct_.get('Diện tích đất công nhận', None))
        dct.setdefault('Diện tích sử dụng', []).append(dct_.get('Diện tích sử dụng', None))
        dct.setdefault('Đường trước nhà', []).append(dct_.get('Đường trước nhà', None))
        dct.setdefault('Nội thất', []).append(dct_.get('Nội thất', None))
        dct.setdefault('Giấy tờ pháp lý', []).append(dct_.get('Giấy tờ pháp lý', None))

        # Trích xuất tiện ích
        Tien_ich = soup_link.find('div', class_="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3")

        # CHECK 3: Chỉ xử lý tiện ích nếu khối Tien_ich tồn tại
        if Tien_ich:
            tis = Tien_ich.find_all('div', class_="rounded-lg border border-gray-200 bg-white p-4")
            
            for ti in tis:
                col_name_tag = ti.find('h4', class_="text-base font-bold text-gray-800")
                if not col_name_tag:
                    continue
                col_name = col_name_tag.text

                names = ti.find_all('div', class_="group/item flex items-baseline justify-between gap-2")
                
                for name in names:
                    name_tag = name.find('span', class_="inline-block whitespace-nowrap text-xs text-gray-700 transition-transform duration-(--marquee-duration,1s) ease-linear group-hover/item:translate-x-(--marquee-offset,0px)")
                    value_tag = name.find('span', class_="shrink-0 text-sm font-semibold text-primary")
                    if not value_tag or not name_tag:
                        continue
                    
                    value_str = value_tag.text.strip()

                    try:
                        if 'k' in value_str:
                            value = float(value_str.replace('km', '').strip()) * 1000
                        else:
                            value = float(value_str.replace('m', '').strip())
                    except ValueError:
                        value = None

                    dctt.setdefault('Ma_BDS', []).append(Ma_BDS)
                    dctt.setdefault('Loai_tien_ich', []).append(col_name.replace('Gần', '').strip())
                    dctt.setdefault('Ten_tien_ich', []).append(name_tag.text.strip())
                    dctt.setdefault('Khoảng cách', []).append(value)

print(f"Hoàn thành! Đã thu thập được {total_bds} bất động sản.")

# Tạo DataFrame và lưu File
df = pd.DataFrame(dct)
df_tien_ich = pd.DataFrame(dctt)

df.to_csv(path_csv, index=False, encoding='utf-8-sig')
df_tien_ich.to_csv(path_csv_tien_ich, index=False, encoding='utf-8-sig')