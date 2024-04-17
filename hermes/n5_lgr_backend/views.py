from django.shortcuts import render
from django.core.paginator import Paginator
from .models import TestDevice, TestSerialData


def backend(request):
    serials = TestDevice.objects.all()

    if request.method == "POST":
        current_serial = request.POST.get("serials")
        refresh_records = request.POST.get("refreshRecords")
        delete_records = request.POST.get("deleteRecords")

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

        if current_serial or refresh_records:
            message_data = TestSerialData.objects.filter(
                device_serial__serial=current_serial
            )
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
