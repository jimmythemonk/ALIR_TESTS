from django.shortcuts import render
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.views.decorators.cache import cache_page
from .models import TestDevice, TestSerialData


@cache_page(60 * 15)
def backend(request):
    serials = TestDevice.objects.all()

    if request.method == "POST":
        current_serial = request.POST.get("serials")
        refresh_records = request.POST.get("refreshRecords")
        delete_records = request.POST.get("deleteRecords")
        export_data = request.POST.get("exportData")

        if delete_records:
            try:
                record = TestDevice.objects.get(serial=current_serial)
            except TestDevice.DoesNotExist:
                print("Device does not exist")
            else:
                record.delete()

            current_serial = serials.first()
            message_data = TestSerialData.objects.filter(
                device_serial__serial=current_serial
            )

        if current_serial or refresh_records or export_data:
            message_data = TestSerialData.objects.filter(
                device_serial__serial=current_serial
            )

        if export_data:
            csv_data = (
                "seq_num| "
                "msg_gen_ts| "
                "msg type| "
                "cell_id| "
                "cell_id_ts| "
                "actual_temp| "
                "trumi_st| "
                "trumi_st_upd_count| "
                "trumi_st_upd_ts| "
                "trumi_st_trans_count| "
                "reloc_st_trans_count| "
                "stored_st_trans_count| "
                "wifi_aps| "
                "pld_sz| "
                "pld_crc| "
                "header_crc| "
                "xyz_raw\n"
            )
            for item in message_data:
                csv_data += (
                    f"{item.seq_num}| "
                    f"{item.msg_gen_ts}| "
                    f"{item.msg_type}| "
                    f"{item.cell_id}| "
                    f"{item.cell_id_ts}| "
                    f"{item.actual_temp}| "
                    f"{item.trumi_st}| "
                    f"{item.trumi_st_upd_count}| "
                    f"{item.trumi_st_upd_ts}| "
                    f"{item.trumi_st_trans_count}| "
                    f"{item.reloc_st_trans_count}| "
                    f"{item.stored_st_trans_count}| "
                    f"{item.wifi_aps}| "
                    f"{item.pld_sz}| "
                    f"{item.pld_crc}| "
                    f"{item.header_crc}| "
                    f"{item.xyz_raw}| \n"
                )

            export_filename = f"{current_serial}_logger_data.csv"
            # Create a response with the CSV data as a file attachment
            response = HttpResponse(csv_data, content_type="text/csv")
            response["Content-Disposition"] = (
                f'attachment; filename="{export_filename}"'
            )
            return response

    elif request.method == "GET":
        page_number = request.GET.get("page")
        if page_number:
            current_serial = request.GET.get("serial")
            if current_serial:
                message_data = TestSerialData.objects.filter(
                    device_serial__serial=current_serial
                )
        else:
            # Default behavior if no page number is provided
            print("No page number specified")
            current_serial = serials.first()
            message_data = TestSerialData.objects.filter(
                device_serial=current_serial
            ).order_by("-create_at")
    else:
        current_serial = serials.first()
        message_data = TestSerialData.objects.filter(
            device_serial=current_serial
        ).order_by("-create_at")

    # Check for message gaps
    prev_seq_num = None
    for data in message_data:
        data.is_incremental = prev_seq_num is None or prev_seq_num - data.seq_num == 1
        prev_seq_num = data.seq_num

    # Most recent message item is always incremental
    if message_data:
        message_data[0].is_incremental = True

    # Define how many records per page you want to display
    records_per_page = 50
    paginator = Paginator(message_data, records_per_page)

    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "message_data": message_data,
        "serials": serials,
        "current_serial": current_serial,
        "page_obj": page_obj,
    }

    return render(request, "n5_lgr_backend/backend.html", context)
