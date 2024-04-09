import paho.mqtt.client as mqtt
from . import parse_logger_msg
from datetime import datetime
import socket
import time


def on_connect(mqtt_client, userdata, flags, rc, a):
    if rc == 0:
        # print("Connected successfully")
        mqtt_client.subscribe("n5_msgs")
    else:
        print("Bad connection. Code:", rc)


def on_message(mqtt_client, userdata, msg):

    from ..models import TestDevice, TestSerialData

    print(f"New message")
    message = msg.payload.decode()

    try:
        n5_lgr = parse_logger_msg.N5LoggerParse()
        parsed_msg = n5_lgr.parse_msg(message)
    except RuntimeWarning as run_warn:
        print("Save message as unknown type, set device message as data msg in models")
    else:
        lgr_msg_ts = parsed_msg["lgr_msg_ts"]
        device_id = parsed_msg["device_id"]
        data_msg = parsed_msg["data_msg"]
        msg_type = parsed_msg["msg_type"]
        flags = parsed_msg["flags"]
        seq_num = parsed_msg["seq_num"]
        msg_gen_ts = parsed_msg["msg_gen_ts"]
        cell_id = parsed_msg["cell_id"]
        cell_id_ts = parsed_msg["cell_id_ts"]
        actual_temp = parsed_msg["actual_temp"]
        trumi_st = parsed_msg["trumi_st"]
        trumi_st_upd_count = parsed_msg["trumi_st_upd_count"]
        trumi_st_upd_ts = parsed_msg["trumi_st_upd_ts"]
        payload = parsed_msg["payload"]

        item = TestDevice(serial=device_id)
        item.save()

        item = TestSerialData(
            lgr_msg_ts=lgr_msg_ts,
            device_serial=TestDevice.objects.get(serial=device_id),
            data_msg=data_msg,
            msg_type=msg_type,
            flags=flags,
            seq_num=seq_num,
            msg_gen_ts=msg_gen_ts,
            cell_id=cell_id,
            cell_id_ts=cell_id_ts,
            actual_temp=actual_temp,
            trumi_st=trumi_st,
            trumi_st_upd_count=trumi_st_upd_count,
            trumi_st_upd_ts=trumi_st_upd_ts,
            payload=payload,
        )
        item.save()


client = mqtt.Client(
    client_id="Foley101",
    transport="tcp",
    protocol=mqtt.MQTTv5,
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
)

client.on_connect = on_connect
client.on_message = on_message

retries = 0
while not client.is_connected():
    retries += 1
    print(f"{datetime.now()}: Sleeping")
    time.sleep(900)
    print(f"{datetime.now()}: Connection failed. Retrying...{retries}")
    try:
        client.connect(host="16.171.79.146", port=1883, keepalive=60)
    except socket.timeout:
        print(f"{datetime.now()}: Connection attempt timed out.")
        continue
    except Exception as e:
        print(f"{datetime.now()}: Error: {e}")
        break

print(f"Connected to the mqtt broker @ 16.171.79.146")
