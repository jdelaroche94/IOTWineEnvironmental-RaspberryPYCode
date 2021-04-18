####IoT ENVIRONMENTAL MONITOR PYTHON CODE v1.0 - 10/11/2019
####The purpose of this code is to read sensor information about temperature, light, humidity and location to provide information
#### that can be used by an IOS application to alert users in case some of the parameters are out of range. This code also provides
#### provides functionality to a LCD screen which is used to alert users on site.
#### This code was designed by Julian De La Roche and Nick Ghulap.
from smbus2 import SMBusWrapper
from threading import *
import string
import math
from RPi import GPIO
from RPLCD import CharLCD
import Adafruit_DHT
import smbus
import time
import firebase_admin
import google.cloud
from datetime import datetime
from firebase_admin import credentials, firestore
import requests
import os

#### FIREBASE CONNECTION
# Credentials and Firebase App initialization. Always required
firCredentials = credentials.Certificate('/home/pi/wem/ServiceAccountKey.json')
firApp = firebase_admin.initialize_app(firCredentials)
# Get access to Firestore
firStore = firestore.client()

#### IOT VARIABLES
# Defining IOT ID
IOTID = '0001'
dateTimeObj = datetime.now()
RULES = []
DEFAULTALERTS = []

####IOT STRUCTURES
# Struct to manage sensor connection
SENSOR_STATUS = {
    "internetConnection": True,
    "htConnection": True,
    "gpsConnection": True,
    "rgbConnection": True
}

# Struct with the IOT information
IOT = {
    "iotId": IOTID,
    "iotName": 'Wine Sensor 2',
    "password": '12345678'
}

# Structure to manage GPS
GPS = {
    "iotId": IOTID,
    "date": dateTimeObj,
    "latitude": 0.0,
    "longitude": 0.0
}

# Structure to manage humidity and temperature
HT = {
    "iotId": IOTID,
    "date": dateTimeObj,
    "humidityDegrees": 0,
    "tempDegrees": 0.0
}

# Structure to manage RGB sensor
RGB = {
    "iotId": IOTID,
    "date": dateTimeObj,
    "red": 0,
    "green": 0,
    "blue": 0
}

#### LCD VARIABLES AND STRUCTURE
# LCD Buffer
framebuffer = [
    '',
    '',
]

# LCD screen configuration
lcd = CharLCD(pin_rs=37, pin_e=35, pins_data=[33, 31, 29, 23],
              numbering_mode=GPIO.BOARD,
              cols=16, rows=2, dotsize=8,
              charmap='A02',
              auto_linebreaks=True)


####DEFAULT ALERTS STRUCTURE
# This method allows to create default alerts, used when a sensor is disable
def createDefaultAlerts():
    rIC = {
        "alertMessage": "IoT Internet offline",
        "alertStatus": "Active",
        "humidityValue": 0,
        "humidityViolation": False,
        "temperatureValue": 0,
        "temperatureViolation": False,
        "lightValue": 0,
        "lightViolation": False,
        "ruleId": IOTID,
        "ruleName": "IoT Rule",
        "severity": "Red",
        "iotId": IOTID,
        "userId": IOTID
    }
    rGPS = {
        "alertMessage": "GPS sensor disable",
        "alertStatus": "Active",
        "humidityValue": 0,
        "humidityViolation": False,
        "temperatureValue": 0,
        "temperatureViolation": False,
        "lightValue": 0,
        "lightViolation": False,
        "ruleId": IOTID,
        "ruleName": "IoT Rule",
        "severity": "Red",
        "iotId": IOTID,
        "userId": IOTID
    }
    rHT = {
        "alertMessage": "Humidity - Temperature sensor disable",
        "alertStatus": "Active",
        "humidityValue": 0,
        "humidityViolation": True,
        "temperatureValue": 0,
        "temperatureViolation": True,
        "lightValue": 0,
        "lightViolation": False,
        "ruleId": IOTID,
        "ruleName": "IoT Rule",
        "severity": "Red",
        "iotId": IOTID,
        "userId": IOTID
    }
    rRGB = {
        "alertMessage": "Light sensor disable",
        "alertStatus": "Active",
        "humidityValue": 0,
        "humidityViolation": False,
        "temperatureValue": 0,
        "temperatureViolation": False,
        "lightValue": 0,
        "light_Violation": True,
        "ruleId": IOTID,
        "ruleName": "IoT Rule",
        "severity": "Red",
        "iotId": IOTID,
        "userId": IOTID
    }
    DEFAULTALERTS.append(rIC)
    DEFAULTALERTS.append(rGPS)
    DEFAULTALERTS.append(rHT)
    DEFAULTALERTS.append(rRGB)


#### BASIC VALIDATION METHODS
# This method validates if a string is float.
def isFloat(value):
    try:
        float(value)
        return True
    except ValueError:
        return False


# This method allows to determine if internet is available or not
def isInternetAvailable():
    try:
        if requests.get('https://google.com').ok:
            SENSOR_STATUS["internetConnection"] = True
        else:
            SENSOR_STATUS["internetConnection"] = False
    except:
        SENSOR_STATUS["internetConnection"] = False
    return SENSOR_STATUS["internetConnection"]


#### LCD METHODS
# This method allows to write in scroll mode in the LCD screen - Taken from circuitbasics.com
def loop_string(string, lcd, framebuffer, row, num_cols, delay=0.3):  # DELAY= CONTROLS THE SPEED OF SCROLL
    padding = ' ' * num_cols
    s = padding + string + padding
    for i in range(len(s) - num_cols + 1):
        framebuffer[row] = s[i:i + num_cols]
        write_to_lcd(lcd, framebuffer, num_cols)
        time.sleep(delay)


# This method allows write by columns in the LCD screen - Taken from circuitbasics.com
def write_to_lcd(lcd, framebuffer, num_cols):
    lcd.home()
    for row in framebuffer:
        lcd.write_string(row.ljust(num_cols)[:num_cols])
        lcd.write_string('\r\n')


#### METHODS FOR GENERAL USE
# This method allows to obtain all the online users which are connected to this specific IoT device.
def obtainIOTUsers():
    users = []
    try:
        if isInternetAvailable():
            onlineUsers = firStore.collection(u'UserIoTLink').stream()
            for ref in onlineUsers:
                link = ref.to_dict()
                if link['iotId'] == IOTID:
                    users.append(link['userId'])
    except:
        pass
    return users


# This method allows to register this IoT device for first. It is only called once on new devices.
def registerIOT():
    if isInternetAvailable():
        firCollectionRef = firStore.collection(u'IOT')
        firCollectionRef.add(IOT)


#### READING SENSOR METHODS
# This method allows to obtain latitude and longitude from the GPS sensor
def obtainGPS():
    latitude = 0.0
    longitude = 0.0
    unichr = chr
    ADDR = 16
    BUS = 1
    complete_strng = ""
    b_run = True
    count = 0
    try:
        while (b_run):
            with SMBusWrapper(BUS) as bus:
                block = bus.read_i2c_block_data(ADDR, 0, 16)
                char_list = [str(unichr(block[i])) for i in range(len(block))]
                raw_strng = "".join(char_list)
                if all(x == "\n" for x in char_list) or count == 30:
                    b_run = False
                else:
                    clean_strng = raw_strng.replace('\r', '').replace('\n', '')
                    complete_strng = complete_strng + clean_strng
                    count = count + 1
        gpsLines = complete_strng.split('$')
        for line in gpsLines:
            gpsLine = line.split(',')
            if gpsLine[0] == 'GNGGA':
                if len(gpsLine) >= 6:
                    if gpsLine[2] != '':
                        if isFloat(gpsLine[2]):
                            latitude = float(gpsLine[2]) / 100
                        if gpsLine[3] == 'S':
                            latitude = latitude * (-1)
                    if gpsLine[4] != '':
                        if isFloat(gpsLine[4]):
                            longitude = float(gpsLine[4]) / 100
                        if gpsLine[5] == 'W':
                            longitude = longitude * (-1)
    except:
        pass
    return [latitude, longitude]


# This method allows to obtain a humidity and temperature measure from the HT sensor
def obtainHT():
    DHT_SENSOR = Adafruit_DHT.AM2302
    DHT_PIN = 4
    humidity1 = -1
    temperature1 = -1
    humidity, temperature = Adafruit_DHT.read_retry(DHT_SENSOR, DHT_PIN)
    if humidity is not None and temperature is not None:
        humidity1 = math.ceil(humidity)
        temperature1 = math.ceil(temperature)
        SENSOR_STATUS["htConnection"] = True
    else:
        SENSOR_STATUS["htConnection"] = False
    return [humidity1, temperature1]


# This method allows to obtain a light measure from the RGB sensor - Part of the code of this method was taken from Lab 7b
def obtainRGB():
    RGB_ADDRESS = 0x29
    RGB_VERSION = 0x44
    red = -1
    green = -1
    blue = -1
    try:
        # Setup SMBus
        bus = smbus.SMBus(1)
        # Enable Color Sensor
        rgbEnabled = False
        bus.write_byte(RGB_ADDRESS, 0x80 | 0x12)
        ver = bus.read_byte(RGB_ADDRESS)
        if ver == RGB_VERSION:
            rgbEnabled = True
            bus.write_byte(RGB_ADDRESS, 0x80 | 0x00)
            bus.write_byte(RGB_ADDRESS, 0x01 | 0x02)
            bus.write_byte(RGB_ADDRESS, 0x80 | 0x14)
        if rgbEnabled:
            data = bus.read_i2c_block_data(RGB_ADDRESS, 0)
            clear = data[1] << 8 | data[0]
            red = data[3] << 8 | data[2]
            green = data[5] << 8 | data[4]
            blue = data[7] << 8 | data[6]
            SENSOR_STATUS["rgbConnection"] = True
        else:
            SENSOR_STATUS["rgbConnection"] = False
    except:
        SENSOR_STATUS["rgbConnection"] = False
    return [red, green, blue]


# This method calls the read GPS method in certain periods of time, and send this information to firebase.
def manageGPS():
    try:
        while (True):
            coordinates = obtainGPS()
            if coordinates[0] != 0.0 and coordinates[1] != 0.0:
                dateTimeObj = datetime.now()
                latitude = coordinates[0]
                longitude = coordinates[1]
                GPS['latitude'] = latitude
                GPS['longitude'] = longitude
                GPS['date'] = dateTimeObj
                SENSOR_STATUS["gpsConnection"] = True
                try:
                    if isInternetAvailable():
                        firCollectionRef = firStore.collection(u'GPS')
                        firCollectionRef.add(GPS)
                except:
                    pass
            else:
                SENSOR_STATUS["gpsConnection"] = False
            time.sleep(10)
    except:
        pass


# This method calls the read HT method in certain periods of time, and send this information to firebase.
def manageHT():
    try:
        while (True):
            ht = obtainHT()
            if ht[0] != -1:
                htConnection = True
                if HT['humidityDegrees'] != ht[0] or HT['tempDegrees'] != ht[1]:
                    dateTimeObj = datetime.now()
                    HT['humidityDegrees'] = ht[0]
                    HT['tempDegrees'] = ht[1]
                    HT['date'] = dateTimeObj
                    try:
                        if isInternetAvailable():
                            firCollectionRef = firStore.collection(u'TemperatureHumidity')
                            firCollectionRef.add(HT)
                    except:
                        pass
            time.sleep(4)
    except:
        pass


# This method calls the read RGB method in certain periods of time, and send this information to firebase.
def manageRGB():
    try:
        while (True):
            light = obtainRGB()
            if light[0] != -1:
                dateTimeObj = datetime.now()
                rUp = light[0] + 100
                rDown = light[0] - 100
                rgbConnection = True
                if RGB['red'] < rDown or RGB['red'] > rUp:
                    dateTimeObj = datetime.now()
                    RGB['red'] = light[0]
                    RGB['green'] = light[1]
                    RGB['blue'] = light[2]
                    RGB['date'] = dateTimeObj
                    try:
                        if isInternetAvailable():
                            firCollectionRef = firStore.collection(u'RGB')
                            firCollectionRef.add(RGB)
                    except:
                        pass
            time.sleep(30)
    except:
        pass


#### RULES AND ALERTS METHODS
# This method allows to update rules on the IoT device when Internet is available.
def updateRules():
    try:
        if isInternetAvailable():
            onlineRules = firStore.collection(u'Rule').stream()
            RULES.clear()
            for ref in onlineRules:
                ruleId = ref.id
                rule = ref.to_dict()
                flag = 0
                if rule['iotId'] == IOTID:
                    tempRule = {
                        "id": ruleId,
                        "humidity": rule['humidity'],
                        "humidity_min": rule['humidity_min'],
                        "humidity_max": rule['humidity_max'],
                        "temperature": rule['temperature'],
                        "temperature_min": rule['temperature_min'],
                        "temperature_max": rule['temperature_max'],
                        "light": rule['light'],
                        "light_intense": rule['light_intense'],
                        "ruleMessage": rule['ruleMessage'],
                        "severity": rule['severity'],
                        "userId": rule['userId']
                    }
                    RULES.append(tempRule)
    except:
        pass


# This method allows to print alerts using the LCD screen as soon as on measure is out of this rule.
def printAlerts():
    if RULES != []:
        for rule in RULES:
            flag = 0
            if rule['humidity'] == True and SENSOR_STATUS["htConnection"] and isFloat(rule['humidity_min']) and isFloat(
                    rule['humidity_max']):
                if HT['humidityDegrees'] < rule['humidity_min'] or HT['humidityDegrees'] > rule['humidity_max']:
                    loop_string(rule['ruleMessage'], lcd, framebuffer, 0, 16)
                    flag = 1
            if rule['temperature'] == True and SENSOR_STATUS["htConnection"] and isFloat(
                    rule['temperature_min']) and isFloat(rule['temperature_max']) and flag == 0:
                if HT['tempDegrees'] < rule['temperature_min'] or HT['tempDegrees'] > rule['temperature_max']:
                    loop_string(rule['ruleMessage'], lcd, framebuffer, 0, 16)
                    flag = 1
            if rule['light'] == True and SENSOR_STATUS["rgbConnection"] and isFloat(
                    rule['light_intense']) and flag == 0:
                light_min = 0
                light_max = 0
                if rule['light_intense'] >= 0 and rule['light_intense'] < 1000:
                    light_min = 0
                    light_max = 999
                if rule['light_intense'] >= 1000 and rule['light_intense'] < 10000:
                    light_min = 1000
                    light_max = 9999
                if rule['light_intense'] >= 10000:
                    light_min = 10000
                    light_max = 70000
            if RGB['red'] < light_min or RGB['red'] > light_max:
                loop_string(rule['ruleMessage'], lcd, framebuffer, 0, 16)
    if DEFAULTALERTS != []:
        if not isInternetAvailable():
            loop_string(DEFAULTALERTS[0]['alertMessage'], lcd, framebuffer, 0, 16)
        if not SENSOR_STATUS["gpsConnection"]:
            sendAlertToFirebase(1)
            loop_string(DEFAULTALERTS[1]['alertMessage'], lcd, framebuffer, 0, 16)
        if not SENSOR_STATUS["htConnection"]:
            sendAlertToFirebase(2)
            loop_string(DEFAULTALERTS[2]['alertMessage'], lcd, framebuffer, 0, 16)
        if not SENSOR_STATUS["rgbConnection"]:
            sendAlertToFirebase(3)
            loop_string(DEFAULTALERTS[3]['alertMessage'], lcd, framebuffer, 0, 16)


# This method allows to send information about default alerts, in case one sensor is disabled. This alert is created to all users connected to this device.
def sendAlertToFirebase(alertNumber):
    users = obtainIOTUsers()
    if users != []:
        for user in users:
            DEFAULTALERTS[alertNumber]['userId'] = user
            try:
                if isInternetAvailable():
                    firCollectionRef = firStore.collection(u'Alert')
                    activeAlert = False
                    for ref in firCollectionRef.stream():
                        link = ref.to_dict()
                        if link['iotId'] == IOTID and link['alertMessage'] == DEFAULTALERTS[alertNumber][
                            'alertMessage'] and link['alertStatus'] == "Active":
                            activeAlert = True
                    if not activeAlert:
                        firCollectionRef.add(DEFAULTALERTS[alertNumber])
            except:
                pass


# This method calls the Update Rules method in certain periods of time.
def manageUpdateRules():
    try:
        while (True):
            updateRules()
            time.sleep(10)
    except:
        pass


# This method calls the Print Alerts method in certain periods of time.
def managePrintAlerts():
    try:
        while (True):
            printAlerts()
            time.sleep(10)
    except:
        pass


#### DASHBOARD METHODS
# This method creates the dashboard on the screen to visualize sensor status.
def dashboard():
    try:
        # os.system("clear")
        while (True):
            os.system("clear")
            print("###################################################################")
            print("#                                                                 #")
            print("#          Welcome to Wine IOT Environmental Monitor              #")
            print("#                                                                 #")
            print("###################################################################")
            print("\n")
            print("  1.  Information about IOT device                                 ")
            print("      a. IoT name: " + IOT['iotName'] + "                           ")
            print("      b. IoT software version: 1.0                                 ")
            if SENSOR_STATUS['internetConnection']:
                print("      c. IoT Internet Status: Online" + "                       ")
            else:
                print("      c. IoT Internet Status: Offline" + "                       ")
            print("  2.  Information about sensor measures                            ")
            if SENSOR_STATUS['rgbConnection']:
                if RGB['red'] < 1000:
                    print("      a. Light: Dark")
                if RGB['red'] >= 1000 and RGB['red'] < 10000:
                    print("      a. Light: Cloudy")
                if RGB['red'] >= 10000:
                    print("      a. Light: Bright")
            else:
                print("      a. Light - Not Available")
            if SENSOR_STATUS['htConnection']:
                print("      b. Temperature: {0:0.1f}*C".format(HT['tempDegrees']))
                print("      c. Humidity: {0:0.1f}%".format(HT['humidityDegrees']))
            else:
                print("      b. Temperature - Not Available")
                print("      c. Humidity - Not Available")
            if SENSOR_STATUS['gpsConnection']:
                print("      d. Location - Latitude: " + str(GPS['latitude']) + " and Longitude: " + str(
                    GPS['longitude']))
            else:
                print("      d. Location - Not Available")
            time.sleep(10)
    except KeyboardInterrupt:
        print('Program exiting')


####CALLING GENERAL METHODS
# Clearing the LCD screen to start
write_to_lcd(lcd, framebuffer, 16)

# Creating default alerts for disable sensors
createDefaultAlerts()

# Disabling GPIO Warning
GPIO.setwarnings(False)
os.system("clear")

####DEFINING THREADS INTO THE DEVICE
# Defining a thread for the GPS sensor
threadGPS = Timer(10.0, manageGPS)

# Defining a thread for the Humidity - Temperature sensor
threadHT = Timer(4.0, manageHT)

# Defining a thread for the RGB sensor
threadRGB = Timer(5.0, manageRGB)

# Defining a thread for Updating Rules from Firebase
threadUpdateRules = Timer(10.0, manageUpdateRules)

# Defining a thread for Print Alerts based on actual readings
threadPrintAlerts = Timer(10.0, managePrintAlerts)

# Defining a thread for Console Dashboard
threadDashboard = Timer(10.0, dashboard)

# Starting Threads
threadGPS.start()
threadHT.start()
threadRGB.start()
threadUpdateRules.start()
threadPrintAlerts.start()
threadDashboard.start()

