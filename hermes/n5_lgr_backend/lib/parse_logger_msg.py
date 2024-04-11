import re
from datetime import datetime, timedelta
import binascii


class N5LoggerParse:
    def __init__(self) -> None:
        self.pattern = pattern = (
            r"(\w{3}\s+\w{3}\s+\d{1,2} \d{2}:\d{2}:\d{2} \d{4}) : Msg: (.*)"
        )
        self.header_format = {
            "device_id": {"size": 12, "ascii": True},
            "msg_type": {
                "size": 2,
                "enum": [
                    "SIGFOX_UPLINK",
                    "FILE_ACTION",
                    "DIAG_DEPRECATED",
                    "BOOT_INFO",
                    "IBEACON_SCAN",
                    "MESSAGE_LIST",
                    "CORE_MSG_UPLINK",
                ],
            },
            "flags": {"size": 2},
            "seq_num": {"size": 8},
            "msg_gen_ts": {"size": 8, "timestamp": True},
            "cell_id": {"size": 8, "hex": True},
            "cell_id_ts": {"size": 8, "timestamp": True},
            "actual_temp": {"size": 2},
            "trumi_st": {
                "size": 2,
                "enum": [
                    "TRUMI_STATE_UNKNOWN",
                    "TRUMI_STATE_SLEEP",
                    "TRUMI_STATE_MOTION_DETECTION",
                    "TRUMI_STATE_RELOCATION ",
                ],
            },
            "trumi_st_upd_count": {"size": 4},
            "trumi_st_upd_ts": {"size": 8, "timestamp": True},
            "payload": {"size": 2},  # DEFAULT TO AS THIS WILL CHANGE ANYWAY WHEN FOUND
        }

    def parse_msg(self, message):
        # Match the pattern in the input string
        match = re.match(self.pattern, message)

        # Extract timestamp and message data
        if match:
            timestamp = match.group(1)
            msg_data = match.group(2)
        else:
            raise RuntimeWarning("Message does not match pattern!")

        parsed_msg_dict = {"data_msg": msg_data, "lgr_msg_ts": timestamp}

        data_pos = 0
        for field, field_settings in self.header_format.items():
            field_msg = msg_data[data_pos : data_pos + field_settings["size"]]

            field_settings_keys = field_settings.keys()
            field_msg_int = int(field_msg, 16)

            if "enum" in field_settings_keys:
                try:
                    field_msg = field_settings["enum"][field_msg_int]
                except KeyError:
                    field_msg = f"Unknown enum value: {field_msg_int}"

            elif "timestamp" in field_settings_keys:
                if field_msg_int != 0:
                    ts_delta = timedelta(seconds=field_msg_int)
                    epoch_offset = datetime(2000, 1, 1)
                    timestamp = epoch_offset + ts_delta
                    field_msg = timestamp.strftime("%a, %B %d, %Y %I:%M:%S %p")
                else:
                    field_msg = "No timestamp"
            elif field == "payload":
                payload = msg_data[data_pos:]
                # todo: need to parse payload
                field_msg = self.parse_payload(payload)
            else:
                if "hex" in field_settings_keys:
                    field_msg = field_msg
                elif "ascii" in field_settings_keys:
                    field_msg = binascii.unhexlify(field_msg).decode("utf-8")
                else:
                    field_msg = field_msg_int

            data_pos += field_settings["size"]

            parsed_msg_dict.update({field: field_msg})

            if field == "msg_type" and field_msg == "BOOT_INFO":
                # Convert hex string to bytes
                hex_bytes = binascii.unhexlify(msg_data[data_pos:])
                # Convert bytes to ASCII while skipping non-ASCII characters
                boot_msg = "".join(chr(byte) for byte in hex_bytes if byte < 128)

                parsed_msg_dict.update({"payload": boot_msg})
                break

            if field == "actual_temp":
                if field_msg == 255:
                    field_msg = "Not Implemented yet."

        # Set keys that have not been populated to default value of null string
        for key in self.header_format:
            if key not in parsed_msg_dict:
                parsed_msg_dict[key] = ""

        return parsed_msg_dict

    def parse_payload(self, payload):
        binary_data = binascii.unhexlify(payload)

        xyz_data = ""

        # Iterate over binary data in chunks of 6 bytes
        for i in range(0, len(binary_data), 6):
            # Extract XYZ value from the chunk
            xyz_bytes = binary_data[i : i + 6]

            # Interpret XYZ bytes (assuming little-endian encoding)
            x = int.from_bytes(xyz_bytes[0:2], byteorder="little", signed=True)
            y = int.from_bytes(xyz_bytes[2:4], byteorder="little", signed=True)
            z = int.from_bytes(xyz_bytes[4:6], byteorder="little", signed=True)

            # Print XYZ values
            xyz_data += f"X: {x} Y: {y} Z: {z}, \n"
            # Remove last comma
            xyz_data = xyz_data[:-1]

        return xyz_data


if __name__ == "__main__":
    n5lgr = N5LoggerParse()
    # message = "Mon Apr  8 07:32:39 2024 : Msg: 4845574748500000000003602da65a14022f2bcf2da6515fff02000000000000d0ff280022fcd1ff280022fcd2ff280022fcd2ff280022fcd1ff280022fcd1ff280022fcd0ff280021fcd0ff290020fcd0ff290020fcd1ff280021fcd0ff280021fcd0ff280021fcd0ff270022fccfff280023fccfff270024fccfff270025fccfff270026fccfff270026fccfff270025fccfff270025fcd0ff270026fcd1ff270026fcd2ff270025fcd1ff280024fcd0ff280023fcd0ff280022fcd0ff280022fcd0ff270022fccfff270022fccfff260022fcd0ff270022fcd0ff290021fcd6ff2a0022fcd5ff290022fcd4ff290022fcd2ff290023fcd1ff280023fcd2ff270023fcd2ff260024fcd2ff260025fcd2ff260025fcd2ff260025fcd2ff260025fcd2ff270025fcd2ff270024fcd3ff280025fcd3ff290025fcd3ff290024fcd3ff290022fcd3ff290022fcd4ff280023fcd4ff280023fcd4ff280022fcd4ff280023fcd4ff280023fcd4ff290023fcd3ff280023fcd4ff270022fcd5ff270022fcd5ff270023fcd5ff270022fcd4ff270022fcd2ff270022fcd2ff280023fcd2ff290020fcd2ff2a001ffcd2ff2a001ffcd3ff290020fcd4ff280020fcd3ff270021fcd3ff270023fcd3ff270023fcd2ff270023fcd3ff280023fcd3ff280023fcd3ff290023fcd2ff280023fcd2ff270023fcd1ff280024fcd1ff280024fcd1ff280024fcd2ff290024fcd3ff290023fcd3ff290023fcd3ff290023fcd4ff290023fcd5ff290022fcd4ff280021fcd4ff280021fcd4ff280020fcd4ff280020fcd3ff290020fcd4ff290020fcd5ff290021fcd4ff280022fcd4ff280023fcd4ff2a0022fcd5ff290022fcd5ff290021fcd4ff290020fcd4ff2a0020fcd4ff2b0020fcd3ff2b001ffcd3ff2a0020fcd4ff290021fcd3ff280023fcd3ff290024fcd3ff290023fcd2ff290023fcd3ff290022fcd4ff280022fcd5ff280022fcd5ff280023fcd4ff280024fcd4ff280024fcd5ff280025fcd6ff290024fcd6ff2a0022fcd6ff2a0021fcd6ff2a0022fcd6ff290023fcd7ff290023fcd7ff2a0022fcd7ff290022fcd6ff290021fcd6ff280021fcd5ff280022fcd5ff280022fcd4ff280021fcd3ff290021fcd3ff290021fcd2ff290021fcd2ff280022fcd1ff280023fcd1ff280023fcd2ff270023fcd4ff260023fcd5ff270025fcd5ff270025fcd5ff270025fcd4ff270026fcd3ff260026fcd4ff260027fcd3ff260027fcd3ff260027fcd2ff260027fcd3ff270025fcd2ff270023fcd2ff270022fcd2ff270022fcd1ff270022fcd0ff280022fcd1ff280022fcd2ff280022fcd3ff280022fcd3ff270023fcd3ff260023fcd3ff260023fcd4ff260023fcd5ff260023fc"
    # message = "Thu Apr  4 09:59:09 2024 : Msg: 4845574748500000000000882da13666022f2bcf2da13644ff00000000000000d8ff14001efc"
    # message = "Thu Apr  4 09:58:29 2024 : Msg: 4845574748500300220000100e000000004445565f42550000000024fb03005900bd02010000003f010100987325056fb004000000000002424336364e4144415230324130315f30312e3030322e30312e303032000001302e302e342c302e302e3400000000000000000000000000"
    # message = "Mon Apr  8 10:59:24 2024 : Msg: 4845574748500000000000002da68a89022f2bcf2da68a62ff00000000000000040012001bfc"
    msg_list = [
        # "Thu Apr  4 10:39:58 2024 : Msg: 4845574748500300220000100e000000004445565f42550000000024fb03005900bd02010000003f010100987325056fb004000000000002424336364e4144415230324130315f30312e3030322e30312e303032000001302e302e342c302e302e3400000000000000000000000000",
        # "Thu Apr  4 09:58:29 2024 : Msg: 4845574748500300220000100e000000004445565f42550000000024fb03005900bd02010000003f010100987325056fb004000000000002424336364e4144415230324130315f30312e3030322e30312e303032000001302e302e342c302e302e3400000000000000000000000000",
        # "Thu Apr  4 09:59:09 2024 : Msg: 4845574748500000000000882da13666022f2bcf2da13644ff00000000000000d8ff14001efc",
        # "Thu Apr  4 10:04:21 2024 : Msg: 4845574748500000000000892da1379d022f2bcf2da1366cff01000000000000daff130020fcdaff130021fcd9ff15001efcd9ff16001efcd8ff17001efcd8ff150020fcd9ff140020fcd8ff14001ffcd7ff15001ffcdaff140020fcd9ff15001dfcd8ff140020fcd8ff150022fcd5ff15001afcd9ff160025fcd8ff140022fcd9ff160020fcd7ff14001ffcdaff170020fcd7ff15001afcd7ff14001dfcd9ff140021fcd8ff140023fcd8ff15001efcd8ff14001efcd8ff150020fcd7ff160025fcd9ff15001dfcd8ff140027fcd7ff14001dfcdaff14001efcd8ff140020fc",
        "Thu Apr  4 10:09:05 2024 : Msg: 48455747485000000000008a2da138b8022f2bcf2da137a4ff01000000000000d8ff130021fcd7ff150020fcd8ff14001efcd9ff160020fcd8ff14001ffcd5ff160021fcd8ff15001dfcd8ff160023fcd9ff130020fcd8ff140020fcd8ff14001ffcd9ff140020fcd9ff14001ffcd8ff16001efcd7ff15001bfcd3ff14001cfcd7ff14001ffcd8ff150021fcd9ff13001efcdaff160019fcd8ff150020fcd8ff12001ffcd7ff14001cfcd8ff14001ffcd8ff170023fcd4ff17003bfcd8ff150022fcd9ff16001ffcdcff130043fcd1ff15001efcdaff14002cfce2ff11002ffc",
    ]
    for message in msg_list:
        parsed_msg = n5lgr.parse_msg(message)

        for key, value in parsed_msg.items():
            print(f"{key}: {value}")
