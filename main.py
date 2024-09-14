from flask import Flask, request, render_template, send_file
import requests
import yaml
import qrcode
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

app = Flask(__name__)


# Function to load settings from YAML
def load_config(config_file="/app/config.yaml"):
    with open(config_file, "r") as file:
        return yaml.safe_load(file)


# Function to login and get session
def login_to_unifi(base_url, username, password):
    session = requests.Session()
    login_endpoint = f"{base_url}/api/login"
    payload = {"username": username, "password": password}
    response = session.post(login_endpoint, json=payload, verify=False)
    return session if response.status_code == 200 else None


# Function to fetch unused vouchers
def get_unused_vouchers(base_url, site, session):
    voucher_endpoint = f"{base_url}/api/s/{site}/stat/voucher"
    response = session.get(voucher_endpoint, verify=False)
    if response.status_code == 200:
        vouchers = response.json().get("data", [])
        return [v for v in vouchers if v.get("used", 0) == 0]
    return []


# Function to generate a Wi-Fi QR code
def generate_wifi_qr(ssid, voucher_code):
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    wifi_string = f"WIFI:S:{ssid};T:WPA;P:{voucher_code};;"
    qr.add_data(wifi_string)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    byte_io = BytesIO()
    img.save(byte_io, format='PNG')
    byte_io.seek(0)
    return byte_io


def calculate_text_height(enable_name_output, line_height):
    # Number of lines of text in a voucher
    text_lines = 3  # SSID, Voucher Code, Duration
    if enable_name_output:
        text_lines += 1  # Hotel
    return (text_lines * line_height)


# Function to calculate dynamic row height with padding
def calculate_row_height(enable_qr_code, enable_name_output, line_height, qr_height, padding=10):
    text_height = calculate_text_height(enable_name_output, line_height)

    if enable_qr_code:
        return text_height + qr_height + padding  # Padding below QR code
    else:
        return text_height + padding  # Extra padding when no QR code


# Function to generate PDF with vouchers
def generate_pdf(vouchers, config, output_file):
    ssid = config["pdf"]["ssid"]
    hotel_name = config["pdf"]["hotel_name"]
    columns = config["pdf"]["columns"]
    enable_qr_code = config["pdf"].get("enable_qr_code", True)
    enable_name_output = config["pdf"].get("enable_name_output", True)  # Default is True if not specified

    c = canvas.Canvas(output_file, pagesize=A4)
    width, height = A4
    margin = 50
    column_width = (width - 2 * margin) / columns
    line_height = 15
    qr_height = 60
    padding = 10

    row_height = calculate_row_height(enable_qr_code, enable_name_output, line_height, qr_height, padding)
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
        duration_days = int(duration_minutes / 1440)

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

        if enable_qr_code:
            qr_code_img = generate_wifi_qr(ssid, code)
            img_reader = ImageReader(qr_code_img)
            c.drawImage(img_reader, x + column_width - 70, y - text_height - qr_height, 60, 60)

        c.rect(x, y - row_height, column_width, row_height)

        x += column_width
        count += 1

    c.save()


# Route to display form
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        config = load_config()
        unifi_config = config["unifi"]

        session = login_to_unifi(unifi_config["base_url"], username, password)
        if session:
            vouchers = get_unused_vouchers(unifi_config["base_url"], unifi_config["site"], session)
            if vouchers:
                output_file = "vouchers.pdf"
                generate_pdf(vouchers, config, output_file)
                return send_file(output_file, as_attachment=True)
            else:
                return "No unused vouchers found"
        else:
            return "Failed to login with provided credentials"

    return render_template("form.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=False)
