# -*- coding: utf-8 -*-

"""
このスクリプトはnem walletのQRコードをキャプチャして認識し、QRコードを生成してAS - 289R2 プリンタシールドで印刷します
"""

import os
import sys
import subprocess
import json
import time
import PIL
import qrcode
import serial
import zbarlight as zb
import wiringpi as wp

LEDPIN = 27 # LEDボタンのLEDのON/OFFをトグルさせるピン 0->1->0と変化させるとLEDの点灯状態が反転する
SWPIN  = 17 # LEDボタンのスイッチ 押すとLowになる

def gpioinit():
    """
    GPIOの初期化
    """
    wp.wiringPiSetupGpio()
    wp.pinMode(LEDPIN, wp.GPIO.OUTPUT)
    wp.pinMode(SWPIN, wp.GPIO.INPUT)
    wp.pullUpDnControl(SWPIN, wp.GPIO.PUD_UP)

def ledtoggle():
    """
    LEDボタンのLEDをトグルさせる
    """
    wp.digitalWrite(LEDPIN, 0)
    time.sleep(0.1)
    wp.digitalWrite(LEDPIN, 1)
    time.sleep(0.1)
    wp.digitalWrite(LEDPIN, 0)

while True:
    gpioinit()

    if wp.digitalRead(SWPIN) == 0:
        """
        押しっぱなしで起動するとLEDに1回信号を送る(状態が反転する)
        """
        ledtoggle()

    captureflag = False
    while captureflag == False:
        print('Taking picture..')
        try:
            f = 1
            qr_count = len(os.listdir('/work'))
            os.system('sudo fswebcam -d /dev/video0 ' +
                    '-r 640x480 -F 1 -S 1 -q /work/qr_' + str(qr_count) + '.jpg')
            print('Picture taken..')
        except:
            f = 0
            print('Picture couldn\'t be taken..')

        print

        if f:
            f = open('/work/qr_' + str(qr_count) + '.jpg', 'rb')
            qr = PIL.Image.open(f)
            qr.load()
            codes = zb.scan_codes('qrcode', qr)
            if codes is None:
                os.remove('/work/qr_' + str(qr_count) + '.jpg')
                print('No QR code found')
            else:
                print('QR codes:', codes)
                captureflag = True

    ledtoggle()
    while wp.digitalRead(SWPIN) == 1:
        time.sleep(0.1)

    print(type(codes))
    print(codes[0].decode('utf-8'))
    qrjson = json.loads(codes[0].decode('utf-8'))
    print(type(qrjson["data"]))
    qrdata = qrjson["data"]
    print('Dict:', qrdata)
    print('List:', qrdata.keys())
    print('Values:', qrdata.values())

    qrname = qrdata["name"]
    qraddr = qrdata["addr"]
    if "amount" in qrdata:
        if type(qrdata["amount"]) == str:
            qramount = int(qrdata["amount"])
        else:
            qramount = qrdata["amount"]
        isamount = True
        print(qramount)
    else:
        isamount = False

    qrcodes = json.dumps(qrjson)
    #qrcodes = re.sub(r"\s+:\s+", ":", qrcodes)
    #qrcodes = re.sub(r"\"\s+,\s+\"", "\",\"", qrcodes)
    #qrcodes = re.sub(r"{\s+\"", "{\"", qrcodes)
    #qrcodes = re.sub(r",\s+\"", ",\"", qrcodes)
    # print(qrcodes)
    # sys.exit()

    QR = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=6,
        border=4,
    )
    QR.add_data(qrcodes)
    QR.make(fit=True)
    image = QR.make_image(fill_color="white", back_color="black")
    image.save('qr.bmp')
    check = subprocess.call(['convert', 'qr.bmp', '-colorspace', 'Gray',
                            '-geometry', '384', '-threshold', '35000', '-colors', '2', '/work/qrcode.bmp'])

    # AS-289R2 Initialize
    ser = serial.Serial("/dev/ttyS0", baudrate=38400, timeout=2)

    # CMD DC2 F
    ser.write(bytes([0x12]))
    ser.write(bytes([0x46]))
    ser.write(bytes([0x36]))

    # Get BMP(384px 384px 1bpp)
    file = open('/work/qrcode.bmp', 'rb')
    file.seek(10)
    offset = ord(file.read(1))
    file.seek(22)
    height = ord(file.read(1))
    height += ord(file.read(1)) * 256

    print("Offset:", offset)
    print("Height:", height)

    # Output CMD
    ser.write(b"Wallet name:")
    ser.write(qrname.encode('utf-8'))
    ser.write(b"\r")
    ser.write(b"Wallet address:")
    ser.write(qraddr.encode('utf-8'))
    ser.write(b"\r")
    if isamount:
        ser.write("このQRコードは請求書です\r".encode('utf-8'))
        ser.write("請求額:".encode('utf-8'))
        ser.write((str(qramount / 1000000.0)).encode('utf-8'))
        ser.write(b" xem\r")

    ser.write(bytes([0x1C]))
    ser.write(bytes([0x2A]))
    ser.write(bytes([0x65]))
    n1 = height / 256
    n2 = height % 256
    print(n1, n2)

    ser.write(bytes([int(n1)]))
    ser.write(bytes([int(n2)]))

    for num in range(height):
        line = height * 48 + offset - ((num + 1) * 48)
        file.seek(line)
        for subnum in range(48):
            x = ord(file.read(1)) ^ 0xFF
            ser.write(bytes([x]))

    for feed in range(6):
        ser.write(bytes([0x0D]))

    file.close()

    ledtoggle()
