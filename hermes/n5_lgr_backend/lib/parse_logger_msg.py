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
            "flags": {"size": 1},
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
            "wifi_aps": {"size": 18},
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

        parsed_msg_dict = {"data_msg": msg_data, "lgr_msg_ts": timestamp}

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
            elif field == "payload":
                payload = msg_data[data_pos:]
                field_msg = self.parse_payload(payload, decompress_payload)
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
        else:
            binary_data = binascii.unhexlify(payload)

        # Iterate over binary data in chunks of 6 bytes
        accel_samples = 0
        for i in range(0, len(binary_data), 6):
            accel_samples += 1
            # Extract XYZ value from the chunk
            xyz_bytes = binary_data[i : i + 6]

            # Interpret XYZ bytes (assuming little-endian encoding)
            x = int.from_bytes(xyz_bytes[0:2], byteorder="little", signed=True)
            y = int.from_bytes(xyz_bytes[2:4], byteorder="little", signed=True)
            z = int.from_bytes(xyz_bytes[4:6], byteorder="little", signed=True)

            # Print XYZ values
            xyz_data += f"X: {x} Y: {y} Z: {z},\n"

        xyz_data = (
            f"{accel_samples} accelerometer samples\n{incorrect_payload}\n{xyz_data}\n"
        )

        return xyz_data

    def _decompress_payload(self, payload: str) -> bytes:

        # Test mode
        # dll = ctypes.CDLL("./hermes/n5_lgr_backend/lib/rice.dll")

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
                # output_buffer = ctypes.create_string_buffer(len(input_buffer) - 2)
                output_buffer = ctypes.create_string_buffer(len(input_buffer))

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
        "Fri Apr 26 11:11:37 2024 : Msg: 505050315a570000000000012dbe47df0015455a2dbe4791ff0200000000000000000000000000000000000000000000000000000000000000000000f51f008a8909048ea7482e8b19401e51ee0e09560b9d02a5b2ea80b9733ae0305dcebc0cd79bb10385eaecb0ed7abb3c3f5e6ed510d7abb5422af75ce08cbe972023afa5c70907e5730241f85cf08e7e1744241f95d20907e973c241fa5cb08e7e5728241f75cf0907d5750241f25d508e7c1750231ed5d208a7ad73c219e95cf086799750211e25d908478176808a0a128b52f704a2d2bd812cb3af584a2ccbdc124b1af884a2bebe4128adaf98492b2be4128ac2f904b2aebe2130aaaf904c2a4be8130a82fb04e29abec13ca52fb04e290bec13ca32fb050284bf01449f2fc852272bf414c9aafd052262bf2148982fc85225cbf6148952ff054248bfc1548f30102991b60385322cc020b04397fc2e1075ff0ba40980608a08140cffbe84c31fefa120c7fbe84433fefa100cffbe04035fef8110cffbe84433fefa110cffbe04833fefa120cffbe84833fef8110dffbe04439fef8110e7fbf04439fefe100d7fbf84431fefe120c7fbf84c33fefc120cffbf04835fefe120d7fbf84835ff0008867fe00120c7fbf84831fefe120c7fbf84833fefe130c7fbf84c31fefe130c7fbf808a08130d7fbe84835fef8110cffbe84433fefc100c7fbf04031fefa110c7fbe04433fefa110cffbe84c33fef6140c7fbd85031fef8140d7fbe85035fefe140d7fbf84c35fefe130cffc002618ff8004c31ff0109867fe00130cffbf84831fefc120c7fbf04c33fefc120cffbf04835fefc120d7fbe84c35fefa130d7fbe84c33fefa120cffbf84833fefe08908130cffbf05033fefe140d7fbf04c35fefa120d7fbe84435fefc110d7fbf04433fefa110cffbe84431fef8110bffbe84831fefc110cffbe84833fefa120cffbe84433fefc110d7fbf04437fefc110dffbe84435fefa110cffbe04831fef8120cffbe04833fefa130d7fbe84835fefa130d7fbe85037fef8150d7fbe05435fefa140dffbe85035fefa8908110d7fbe84435fefa120cffbe84833fefa120cffbf04433fefc120cffbe84c33fefa130c7fbe84c31fefa130cffbe84c35fefa140cffbf04c33fefa130c7fbe84c31fefa130bffbf04831fefc110cffbe84433fefa110cffbe84435fefa100dffbf83c37fefe100d7fbf04435fefa110d7fbe04431fef8110c7fbe84433fefc120cffbf04833fefa"
    ]
    for message in msg_list:
        parsed_msg = n5lgr.parse_msg(message)

        for key, value in parsed_msg.items():
            print(f"{key}: {value}")
