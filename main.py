import requests
import yaml
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import qrcode
from io import BytesIO
import urllib3

# Suppress SSL warning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# Function to load settings from YAML
def load_config(config_file="config.yaml"):
    with open(config_file, "r") as file:
        return yaml.safe_load(file)


# Function to login and get session
def login_to_unifi(base_url, username, password):
    session = requests.Session()
    login_endpoint = f"{base_url}/api/login"
    payload = {"username": username, "password": password}
    try:
        response = session.post(login_endpoint, json=payload, verify=False)
        if response.status_code == 200:
            print("Logged in successfully")
            return session
        else:
            print(f"Failed to login: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error logging in: {e}")
        return None


# Function to fetch unused vouchers
def get_unused_vouchers(base_url, site, session):
    voucher_endpoint = f"{base_url}/api/s/{site}/stat/voucher"
    try:
        response = session.get(voucher_endpoint, verify=False)
        if response.status_code == 200:
            vouchers = response.json().get("data", [])
            unused_vouchers = [v for v in vouchers if v.get("used", 0) == 0]  # Only unused vouchers
            return unused_vouchers
        else:
            print(f"Failed to fetch vouchers: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error fetching vouchers: {e}")
        return []


# Function to generate a Wi-Fi QR code
def generate_wifi_qr(ssid, voucher_code):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    wifi_string = f"WIFI:S:{ssid};T:WPA;P:{voucher_code};;"
    qr.add_data(wifi_string)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    byte_io = BytesIO()
    img.save(byte_io, format='PNG')
    byte_io.seek(0)  # Reset file pointer to the beginning
    return byte_io


def calculate_text_height(enable_name_output, line_height):
    # Number of lines of text in a voucher
    text_lines = 3  # SSID, Voucher Code, Duration
    if enable_name_output:
        text_lines += 1 # Hotel
    return (text_lines * line_height) + 7


# Function to calculate dynamic row height
def calculate_row_height(enable_qr_code, enable_name_output, line_height, qr_height):

    text_height = calculate_text_height(enable_name_output, line_height)

    # Add space for QR code if enabled
    if enable_qr_code:
        return text_height + qr_height
    else:
        return text_height


# Function to generate PDF with vouchers in multiple columns and rows
def generate_pdf(vouchers, config):
    ssid = config["pdf"]["ssid"]
    hotel_name = config["pdf"]["hotel_name"]
    output_file = config["pdf"]["output_file"]
    columns = config["pdf"]["columns"]
    enable_qr_code = config["pdf"].get("enable_qr_code", True)  # Default is True if not specified
    enable_name_output = config["pdf"].get("enable_name_output", True)  # Default is True if not specified

    c = canvas.Canvas(output_file, pagesize=A4)
    width, height = A4
    margin = 50
    column_width = (width - 2 * margin) / columns
    line_height = 15  # Approximate height of a line of text
    qr_height = 60  # Approximate height of the QR code

    # Dynamically calculate the row height based on whether the QR code is enabled
    row_height = calculate_row_height(enable_qr_code, enable_name_output, line_height, qr_height)
    text_height = calculate_text_height(enable_name_output, line_height)

    y = height - margin
    x = margin
    count = 0

    for voucher in vouchers:
        if count % columns == 0 and count != 0:
            y -= row_height
            x = margin

        if y < margin + row_height:
            c.showPage()
            y = height - margin
            x = margin

        code = voucher.get("code", "Unknown")
        duration_minutes = voucher.get("duration", 0)
        duration_days = int(duration_minutes / 1440)  # Convert minutes to full days (no decimal)

        # Draw voucher details in the new order
        if enable_name_output:
            c.drawString(x + 10, y - line_height, f"{hotel_name}")
            c.drawString(x + 10, y - 2 * line_height, f"SSID: {ssid}")
            c.drawString(x + 10, y - 3 * line_height, f"Voucher Code: {code}")
            c.drawString(x + 10, y - 4 * line_height, f"Duration: {duration_days} days")
        else:
            c.drawString(x + 10, y - line_height, f"SSID: {ssid}")
            c.drawString(x + 10, y - 2 * line_height, f"Voucher Code: {code}")
            c.drawString(x + 10, y - 3 * line_height, f"Duration: {duration_days} days")

        # Conditionally generate and add QR code
        if enable_qr_code:
            qr_code_img = generate_wifi_qr(ssid, code)
            img_reader = ImageReader(qr_code_img)
            c.drawImage(img_reader, x + column_width - 70, y - text_height - qr_height, 60, 60)

        # Draw a rectangle around the voucher
        c.rect(x, y - row_height, column_width, row_height)

        # Move to the next column
        x += column_width
        count += 1

    c.save()
    print(f"PDF generated: {output_file}")


if __name__ == "__main__":
    # Load configuration from YAML
    config = load_config()

    unifi_config = config["unifi"]

    # Login to Unifi controller
    session = login_to_unifi(unifi_config["base_url"], unifi_config["username"], unifi_config["password"])
    if session:
        # Fetch unused vouchers
        vouchers = get_unused_vouchers(unifi_config["base_url"], unifi_config["site"], session)

        # Generate PDF with vouchers
        if vouchers:
            print(f"Found {len(vouchers)} vouchers")
            generate_pdf(vouchers, config)
        else:
            print("No unused vouchers found")
