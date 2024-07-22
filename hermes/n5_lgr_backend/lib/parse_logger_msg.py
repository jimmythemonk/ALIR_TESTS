import re
from datetime import datetime, timedelta
import binascii
import ctypes


class N5LoggerParse:
    def __init__(self) -> None:
        self.test_mode = False
        self.pattern = pattern = (
            r"(\w{3}\s+\w{3}\s+\d{1,2} \d{2}:\d{2}:\d{2} \d{4}) : Msg: (.*)"
        )
        self.header_format = {
            "device_id": {"size": 6, "ascii": True},
            "msg_type": {
                "size": 1,
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
            "flags": {
                "size": 1,
                "bits": [
                    {
                        "size": 3,
                        "name": "Trumi Sample Rate",
                        "enum": [
                            "TRUMI_NEXT_EXEC_UNDEFINED",
                            "TRUMI_NEXT_EXEC_ASAP",
                            "TRUMI_NEXT_EXEC_IN_500MS",
                            "TRUMI_NEXT_EXEC_IN_1S",
                            "TRUMI_NEXT_EXEC_IN_10S",
                        ],
                    },
                    {
                        "size": 2,
                        "name": "Trumi Acc Mode",
                        "enum": [
                            "TRUMI_ACC_UNDEFINED",
                            "TRUMI_ACC_SINGLE_SAMPLE",
                            "TRUMI_ACC_100HZ",
                            "TRUMI_ACC_1600HZ",
                        ],
                    },
                ],
            },
            "seq_num": {"size": 4},
            "msg_gen_ts": {"size": 4, "timestamp": True},
            "cell_id": {"size": 4, "hex": True},
            "cell_id_ts": {"size": 4, "timestamp": True},
            "actual_temp": {"size": 1},
            "trumi_st": {
                "size": 1,
                "enum": [
                    "TRUMI_STATE_UNKNOWN",
                    "TRUMI_STATE_SLEEP",
                    "TRUMI_STATE_MOTION_DETECTION",
                    "TRUMI_STATE_RELOCATION ",
                ],
            },
            "trumi_st_upd_count": {"size": 2},
            "trumi_st_upd_ts": {"size": 4, "timestamp": True},
            "trumi_st_trans_count": {"size": 2},
            "reloc_st_trans_count": {"size": 2},
            "stored_st_trans_count": {"size": 2},
            "wifi_aps": {"size": 18, "hex": True},
            "reserved_1": {"size": 2},
            "pld_sz": {"size": 2},
            "pld_crc": {"size": 2, "hex": True},
            "reserved_2": {"size": 1},
            "header_crc": {"size": 1, "hex": True},
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

        parsed_msg_dict = {
            "data_msg": msg_data,
            "lgr_msg_ts": timestamp,
            "xyz_raw": "n/a",
        }

        decompress_payload = False
        data_pos = 0
        for field, field_settings in self.header_format.items():
            bytes_to_char_len = field_settings["size"] * 2
            field_msg = msg_data[data_pos : data_pos + bytes_to_char_len]

            field_settings_keys = field_settings.keys()
            field_msg_int = int(field_msg, 16)

            if "enum" in field_settings_keys:
                try:
                    field_msg = field_settings["enum"][field_msg_int]
                except (KeyError, IndexError):
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

            elif "bits" in field_settings_keys:
                # For "bits", three keys are mandatory -> size, name, enum.
                # Get binary string of value, then reverse so it can be iterated through
                field_bits_rev = format(field_msg_int, "08b")[::-1]

                bit_start = 0
                flag_msg = ""
                for bit_info in field_settings["bits"]:
                    end_bits = bit_start + bit_info["size"]
                    bit_value = int(field_bits_rev[bit_start:end_bits][::-1], 2)
                    bit_start = end_bits
                    try:
                        flag_msg += (
                            f'{bit_info["name"]}: {bit_info["enum"][bit_value]}\n'
                        )
                    except IndexError:
                        flag_msg += (
                            f"Error with bit value: {bit_value} in {bit_info['name']}\n"
                        )

                if flag_msg:
                    field_msg = flag_msg
                else:
                    field_msg = f"Error with flags value: {field_msg}"

            elif field == "actual_temp":
                if field_msg_int == 255:
                    field_msg = "n/a"
                else:
                    actual_temp = (field_msg_int / 2) - 40
                    field_msg = f"{actual_temp} C"
            elif field == "payload":
                payload = msg_data[data_pos:]
                parsed_payload = self.parse_payload(payload, decompress_payload)
                parsed_msg_dict.update({"xyz_raw": parsed_payload["xyz_data_raw"]})
                field_msg = parsed_payload["xyz_data"]
            else:
                if "hex" in field_settings_keys:
                    field_msg = field_msg
                elif "ascii" in field_settings_keys:
                    field_msg = binascii.unhexlify(field_msg).decode("utf-8")
                else:
                    field_msg = field_msg_int

            data_pos += bytes_to_char_len

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
            timestamp_interval_every = 196
        else:
            binary_data = binascii.unhexlify(payload)
            timestamp_interval_every = 10

        # Iterate over binary data in chunks of 6 bytes
        accel_samples = 0
        xyz_bytes = []
        accel_sample_timestamp = ""

        index = 0
        while index < len(binary_data):
            fifo_timestamp = binary_data[index : index + 4]
            field_msg_int = int.from_bytes(fifo_timestamp, byteorder="little")
            ts_delta = timedelta(seconds=field_msg_int)
            epoch_offset = datetime(2000, 1, 1)
            timestamp = epoch_offset + ts_delta
            accel_sample_timestamp = timestamp.strftime("%a, %B %d, %Y %I:%M:%S %p")
            data_p = binary_data[index + 4 : index + timestamp_interval_every]
            index += timestamp_interval_every
            if timestamp_interval_every == 196:
                xyz_data += f"{accel_sample_timestamp},\n"

            for i in range(0, len(data_p), 6):
                accel_samples += 1
                # Extract XYZ value from the chunk
                xyz_bytes = data_p[i : i + 6]

                # Interpret XYZ bytes (assuming little-endian encoding)
                x = int.from_bytes(xyz_bytes[0:2], byteorder="little", signed=True)
                y = int.from_bytes(xyz_bytes[2:4], byteorder="little", signed=True)
                z = int.from_bytes(xyz_bytes[4:6], byteorder="little", signed=True)

                # Print XYZ values
                if timestamp_interval_every == 196:
                    xyz_data += f"[{accel_samples}] X: {x} Y: {y} Z: {z},\n"
                else:
                    xyz_data += f"[{accel_samples}] X: {x} Y: {y} Z: {z}, {accel_sample_timestamp},\n"

        xyz_data = (
            f"{accel_samples} accelerometer samples\n"
            f"{incorrect_payload}\n{xyz_data}\n"
        )
        xyz_data_raw = binascii.hexlify(binary_data).decode("utf-8")
        parsed_payload = {"xyz_data": xyz_data, "xyz_data_raw": xyz_data_raw}

        return parsed_payload

    def _decompress_payload(self, payload: str) -> bytes:

        # Test mode
        if self.test_mode:
            dll = ctypes.CDLL("./hermes/n5_lgr_backend/lib/rice.dll")
        else:
            # Real mode
            dll = ctypes.CDLL("./n5_lgr_backend/lib/rice.so")

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
            fifo_timestamp = payload_data[index + 1 : index + 5]

            index += 5
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
                # Buffer will always be 192 bytes (32 samples * 6 bytes each) in trumi mode
                output_buffer = ctypes.create_string_buffer(192)

                # Call the function
                dll.Rice_Uncompress(
                    input_buffer,
                    output_buffer,
                    len(input_buffer),
                    len(output_buffer),
                    3,
                )

                decompressed_payload["decomp_payload"] += (
                    fifo_timestamp + output_buffer.raw
                )

                # field_msg_int = int.from_bytes(fifo_timestamp, byteorder="little")
                # ts_delta = timedelta(seconds=field_msg_int)
                # epoch_offset = datetime(2000, 1, 1)
                # timestamp = epoch_offset + ts_delta
                # accel_sample_timestamp = timestamp.strftime("%a, %B %d, %Y %I:%M:%S %p")
                # print(
                #     f"{accel_sample_timestamp} - {output_buffer.raw.hex()} ({len(output_buffer.raw.hex())})"
                # )

            index += fifo_length

        return decompressed_payload


if __name__ == "__main__":
    n5lgr = N5LoggerParse()

    # msg_list = [
    #     # "Thu Apr  4 10:39:58 2024 : Msg: 4845574748500300220000100e000000004445565f42550000000024fb03005900bd02010000003f010100987325056fb004000000000002424336364e4144415230324130315f30312e3030322e30312e303032000001302e302e342c302e302e3400000000000000000000000000",
    #     # "Thu Apr  4 09:58:29 2024 : Msg: 4845574748500300220000100e000000004445565f42550000000024fb03005900bd02010000003f010100987325056fb004000000000002424336364e4144415230324130315f30312e3030322e30312e303032000001302e302e342c302e302e3400000000000000000000000000",
    #     # "Thu Apr  4 09:59:09 2024 : Msg: 4845574748500000000000882da13666022f2bcf2da13644ff00000000000000d8ff14001efc",
    #     "Thu Apr  4 10:04:21 2024 : Msg: 4845574748500000000000892da1379d022f2bcf2da1366cff01000000000000daff130020fcdaff130021fcd9ff15001efcd9ff16001efcd8ff17001efcd8ff150020fcd9ff140020fcd8ff14001ffcd7ff15001ffcdaff140020fcd9ff15001dfcd8ff140020fcd8ff150022fcd5ff15001afcd9ff160025fcd8ff140022fcd9ff160020fcd7ff14001ffcdaff170020fcd7ff15001afcd7ff14001dfcd9ff140021fcd8ff140023fcd8ff15001efcd8ff14001efcd8ff150020fcd7ff160025fcd9ff15001dfcd8ff140027fcd7ff14001dfcdaff14001efcd8ff140020fc",
    #     # "Mon Apr 22 08:02:31 2024 : Msg: 505050315a5700000000006c2db8d6150015055b2db8d5ddff020000000000009e07210bfff008421fffe008844fffc000f89fff8001f13fff0083e2bffe010362bffe010362bffe0183a27ffe0184227ffe018422bffe018422bffe0103a23ffe010361fffe0103617ffe0083a0fffe0087c17ffc001083fff8022105fff0083e0bffe010741fffc020f84fff8062109fff0084217ffe0088c47ffc010944fffc0109457ffc0008c4fffc0108c2bffe0104615ff020842bfe0610857fc0c0a0071d0ffff0083a1fffe0107437ffc021086fff806210dfff00c461bffe0104617ffe0104617ffe0184617ffe0104a17ffe0104a1bffe0084a1bffe0084a1fffe008461fffe0083e1fffe0083e23ffe0083e27ffe0083e23ffe0083e1fffe0103e1bffe010421bffe010461bffe010461bffe0084613ffe0084213ffe0084213ffe0083e13ffe0083e13ffe0083e13ffe008841fffc011084fff802210bfff0049f07250dfff000461bffdfe230bffeff1185fff800230bfff0004217ffe0004217ffe0083e13ffe0083e13ffe0084213ffe0104213ffe0104213ffe0104213ffe0104213ffe0104217ffe010421bffe010421bffe0103e1fffe0103e1fffe0183e23ffe0183e23ffe0184227ffe0204223ffe0283e27ffe0203e27ffe0183a27ffe0183a1bffe0103617ffe0003a13ffdfe1f09ffeff0f84fff7f87427ffc000a1071f0ffff0084217ffe0108c37ffc021185fff804210dfff008421fffe010421fffe008421bffe000461bffe0084617ffe0084a1bffe0084a1fffe0084623ffe0084627ffe0104227ffe0084223ffe008420ffff0082306fff8041186fff8041085fff8021085fff8000f86fff8021086fff8021086fff8041187fff8041188fff8021087fff8021086fff8041086fff8061187fff8081186fff8081186fff8080a0072307fff0004a0fffe0008c27ffc001185fff802210dfff0043e1bffe010461fffe0184a27ffe0184a23ffe0184623ffe0184227ffe0104217fff00c1f0afff8060e8afff8040f8afff804108afff8041189fff8021188fff8021087fff8021087fff8041087fff8041085fff8041084fff8020f83fff8001083fff8002107fff000420fffe0088427ffc011086fff800210ffff0041f13fff0081f13fff00c"
    # ]
    msg_list = [
        # "Thu Apr 25 13:28:33 2024 : Msg: 505050315a570000000000122dbd17000016f15b2dbd123eff0200000000000000000000000000000000000000000000000000000000000000000000c65500018d08110dffc04241bff8084835ff010906ffe04110dffc08201aff8104037ff000806bfdfc2219ff8004433ff0008867fe040f0d7fc081e1bff8083c37ff0008067fe00110c7fc002218ff8004033ff0008867fe00120cffc00241aff7f0806ffdfc1e1cff8004037ff010886bfe02120d7fc00261aff8004835fefe110d7fbf84435ff000806bfe000e0dffc0408c08110d7fc042219ff8104433ff0208867fe02120d7fbf84833fefc110d7fbf84435ff010906bfe02120d7fc04241bff8004439fefe0f0dffbf83c37ff000786ffe00100dffc00221bff8004439fefe120dffbf04837fefa110dffbf04437fefe110d7fc04201bff8103c37ff010806ffe00110dffbf84437fefe110d7fc042019ff8104033ff0207867fe0008d08100d7fbf84035ff000806ffe040f0dffc0c201cff8184439ff0208873fe02100dffc00221bff8004035ff000786bfe00100cffbf84435fefe100d7fbf84035ff000806bfe02100d7fc04201aff8083c35ff010806ffe02100dffc04221bff8004837ff010906bfe04120dffc08221bff8004437ff000806bfe00100d7fc041e1bff8104039ff010806ffe0008d08110dffc04241bff8004835ff000886ffdfc221bff8004439ff010886ffe00110dffc00221bff8004037ff000806ffe00110dffc04221bff8104835ff020906bfe02120d7fc002419ff7f08867fdfc241aff8004837ff010906ffe00120e7fc00241dff8004c3bff0109873fe02120e7fc04201cff8004039fefc100dffbf04437fefe120e7fc00241bff8080"
        # "Thu Apr 25 15:17:09 2024 : Msg: 505050315a5700000000002e2dbd30710016f15b2dbd2e0aff0100000000000000000000000000000000000000000000000000000000000000000000cbfa00ab0500edfff6030f00ecfffc030f00ebfffe030e00ebfffd030f00ebfffa030f00e9fffc030f00e9fffc030f00ebfffc030f00e9fffd030f00eafffd030d00ebfffe031000ebff00041000ecfffd031000ecfffe030f00e9fffd030f00e9fffc031000e8ffff030e00eaffff030f00ebfffe030f00eaff00040c00eafffd030e00ebfffe030e00ebfffd030e00e9fffd030e00ebfffd031100e9fffd030e00edfffb031200ebfffe030e00ebfffe030e00ecfffc030f00ecfffe030e00ebfffd030f00ecff00040e00f2ff0a040f00ebfffe030e00eaff00040f00eafffd031000eafffc030e00ebfffd030f00ecfffc030f00ebfffd030f00eafffd030e00eafffc030e00e9fffd030f00e9fff9031000eafffc031100e9fffe031000eafffd030f00ecfffd031200ebfffc030f00e9fffe030d00eafffd030e00ecfffd030f00eafffd030e00eafffb031200ebfffd030e00e8fffc030f00ebfffd030f00eafffd030f00eafffe030f00e9fffd030d00eafffc031000eaff0104f6ffa3ffad040d00e2ffe005",
        "Mon Apr 29 08:24:12 2024 : Msg: 505050315a5700000000000c2dc215aa0015055b2dc21542ff020000000000000000000000000000000000000000000000000000000000000000000060ec00699c070c39fff0001873ffdfe0c37fff000186fffe00038e7ffc01071cfff800071cfff800061cfff800051cfff800051cfff800061cfff7f8186fffdfe061bfff7f830dfffbfc1c6fffe00038dfffc01061afff8000a33ffeff061afff800071cfff802071cfff804071bfff806081cfff804081cfff802081dfff802081dff8101c77fe04071dfff804081efff804081ffff802091ffff800091fff8009e071435ffeff0a1bfff7f850dfffc00091cfff8001239fff0001c6fffe000146fffe000146fffe0001473ffe0001873ffe000186fffe000186fffe0081c73ffe0001877ffdfe051ffff7f8147bffe0001c7bffe000207bffe000207bffdfe081efff7f81c77ffe0001c77ffe0081873ffe0101473ffe0101473ffe0081873ffe0081c73ffe0082073ffe0002077ffdfe081cfff7f82073ffdfc071cfff7f89b071039fff000206fffe00840dfffc00091bfff7f848e7ffbf81c77ffdfc071cfff7f01c77ffe0001c77ffe01038efffc02071dfff802071dfff802071dfff802081dfff800091bfff800081afff8000819ff8082063fe020719ff8001c67ffdfe0619fff7f0186bffdfa071afff7d838dfffbec1c6bffdfa0e35ffeff071afff8000e35fff004186fffe01030e7ffc03028efffc02030efffc02009b070e3bfff0001873ffdfe0c37ffeff061cfff7f838efffc01081cfff804081dfff804071dfff802071efff800071dfff7f82077ffdfc081dfff7f02073ffdfe071dfff7f81877ffdfe0c3bfff0001873ffe00838e7ffc01081cfff802081cfff800081dfff802081eff8081c77fe02071cfff802061bfff802081afff800091afff7f0246fffdfc091cfff7f82473ffdfe091dfff800091dfff7f89b070a37ffeff061cfff7f030dfffbf8186bffdfe0e37ffeff051bfff8000839fff0041077ffe01820f7ffc04020f7ffc03020f7ffc02018f7ffc01018ffffc00010f7ffbfc047bffdfc043bffefe031cfff7f020efffbf80cefffbf80cefffbf81077ffdfc083bffefe041cfff7f020e7ffc00041bfff8040a37fff014106bffe028146bffe020146fffe018146fffe010186fffe0081c6bffe000099071437ffeff0a1cfff8001439fff0082c73ffe01058dfffc000b1cff8002c3bff0005077fe000a0effbf82877fdfc1439ffeff050dfffbf81237ffefe048dfffbf81237ffefd048d7ffbf01037ffefd038e7ffbf41039ffefd038efffbf82073ffdfe1037ffeff081bfff7f82073ffdfe061cfff7f81477ffe0001077ffe0001077ffe0081077ffe0100c7bffe010107bffe0101477ffe0080"
    ]
    n5lgr.test_mode = True
    for message in msg_list:
        parsed_msg = n5lgr.parse_msg(message)

        for key, value in parsed_msg.items():
            if key != "data_msg":
                print(f"{key}: {value}")
