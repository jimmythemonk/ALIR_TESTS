import re
from datetime import datetime, timedelta
import binascii
import ctypes


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
            # If not matched, set all key values to blank string, and only set 3 values to parse
            for key in self.header_format:
                parsed_msg_dict[key] = ""
            parsed_msg["device_id"] = binascii.unhexlify(message[0:12]).decode("utf-8")
            parsed_msg["msg_gen_ts"] = datetime.now()
            parsed_msg["payload"] = message

            return parsed_msg_dict

        parsed_msg_dict = {"data_msg": msg_data, "lgr_msg_ts": timestamp}

        decompress_payload = False
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

                if field == "trumi_st" and field_msg == "TRUMI_STATE_MOTION_DETECTION":
                    decompress_payload = True

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
                field_msg = self.parse_payload(payload, decompress_payload)
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

    def parse_payload(self, payload, decompress_payload):

        xyz_data = ""

        incorrect_payload = ""
        if decompress_payload:
            decompressed_payload = self._decompress_payload(payload)
            binary_data = decompressed_payload["decomp_payload"]
            incorrect_payload = decompressed_payload["fifo_error"]
        else:
            binary_data = binascii.unhexlify(payload)

        # Iterate over binary data in chunks of 6 bytes
        for i in range(0, len(binary_data), 6):
            # Extract XYZ value from the chunk
            xyz_bytes = binary_data[i : i + 6]

            # Interpret XYZ bytes (assuming little-endian encoding)
            x = int.from_bytes(xyz_bytes[0:2], byteorder="little", signed=True)
            y = int.from_bytes(xyz_bytes[2:4], byteorder="little", signed=True)
            z = int.from_bytes(xyz_bytes[4:6], byteorder="little", signed=True)

            # Print XYZ values
            xyz_data += f"X: {x} Y: {y} Z: {z}, "

        xyz_data = xyz_data + payload + incorrect_payload

        return xyz_data

    def _decompress_payload(self, payload: str) -> bytes:

        # Test mode
        # dll = ctypes.CDLL("./hermes/n5_lgr_backend/lib/rice.dll")

        # Real mode
        dll = ctypes.CDLL("./n5_lgr_backend/lib/rice.dll")
        # Define the argument types
        dll.Rice_Uncompress.argtypes = [
            ctypes.c_void_p,  # void* in
            ctypes.c_void_p,  # void* out
            ctypes.c_uint,  # unsigned int insize
            ctypes.c_uint,  # unsigned int outsize
            ctypes.c_int,  # int format
        ]

        # Define the return type
        dll.Rice_Uncompress.restype = None  # The function doesn't return anything

        payload_data = bytes.fromhex(payload)

        payload_len = len(payload_data)

        index = 0
        fifo_num = 0
        decompressed_payload = {"decomp_payload": b"", "fifo_error": ""}
        while index < payload_len:
            fifo_num += 1
            fifo_length = payload_data[index]
            index += 1
            fifo_data_size = index + fifo_length

            if fifo_data_size > payload_len:
                decompressed_payload["fifo_error"] = (
                    f"Error at fifo payload number {fifo_num}"
                )
                break
            else:
                fifo_data = payload_data[index:fifo_data_size]

                input_buffer = ctypes.create_string_buffer(fifo_data)
                # Allocate a buffer for the output
                output_buffer = ctypes.create_string_buffer(len(input_buffer) - 2)

                # Call the function
                dll.Rice_Uncompress(
                    input_buffer,
                    output_buffer,
                    len(input_buffer),
                    len(output_buffer),
                    3,
                )

                decompressed_payload["decomp_payload"] += output_buffer.raw

            index += fifo_length

        return decompressed_payload


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
        "Mon Apr 22 08:02:31 2024 : Msg: 505050315a5700000000006c2db8d6150015055b2db8d5ddff020000000000009e07210bfff008421fffe008844fffc000f89fff8001f13fff0083e2bffe010362bffe010362bffe0183a27ffe0184227ffe018422bffe018422bffe0103a23ffe010361fffe0103617ffe0083a0fffe0087c17ffc001083fff8022105fff0083e0bffe010741fffc020f84fff8062109fff0084217ffe0088c47ffc010944fffc0109457ffc0008c4fffc0108c2bffe0104615ff020842bfe0610857fc0c0a0071d0ffff0083a1fffe0107437ffc021086fff806210dfff00c461bffe0104617ffe0104617ffe0184617ffe0104a17ffe0104a1bffe0084a1bffe0084a1fffe008461fffe0083e1fffe0083e23ffe0083e27ffe0083e23ffe0083e1fffe0103e1bffe010421bffe010461bffe010461bffe0084613ffe0084213ffe0084213ffe0083e13ffe0083e13ffe0083e13ffe008841fffc011084fff802210bfff0049f07250dfff000461bffdfe230bffeff1185fff800230bfff0004217ffe0004217ffe0083e13ffe0083e13ffe0084213ffe0104213ffe0104213ffe0104213ffe0104213ffe0104217ffe010421bffe010421bffe0103e1fffe0103e1fffe0183e23ffe0183e23ffe0184227ffe0204223ffe0283e27ffe0203e27ffe0183a27ffe0183a1bffe0103617ffe0003a13ffdfe1f09ffeff0f84fff7f87427ffc000a1071f0ffff0084217ffe0108c37ffc021185fff804210dfff008421fffe010421fffe008421bffe000461bffe0084617ffe0084a1bffe0084a1fffe0084623ffe0084627ffe0104227ffe0084223ffe008420ffff0082306fff8041186fff8041085fff8021085fff8000f86fff8021086fff8021086fff8041187fff8041188fff8021087fff8021086fff8041086fff8061187fff8081186fff8081186fff8080a0072307fff0004a0fffe0008c27ffc001185fff802210dfff0043e1bffe010461fffe0184a27ffe0184a23ffe0184623ffe0184227ffe0104217fff00c1f0afff8060e8afff8040f8afff804108afff8041189fff8021188fff8021087fff8021087fff8041087fff8041085fff8041084fff8020f83fff8001083fff8002107fff000420fffe0088427ffc011086fff800210ffff0041f13fff0081f13fff00c"
    ]
    for message in msg_list:
        parsed_msg = n5lgr.parse_msg(message)

        for key, value in parsed_msg.items():
            print(f"{key}: {value}")
