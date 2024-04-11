from django.shortcuts import render
from .models import TestDevice, TestSerialData


def backend(request):
    serials = TestDevice.objects.all()

    if request.method == "POST":
        current_serial = request.POST.get("serials")
        if current_serial:
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
        data.is_incremental = prev_seq_num is None or data.seq_num == prev_seq_num + 1
        prev_seq_num = data.seq_num

    # Most recent message item is always incremental
    if message_data:
        message_data[0].is_incremental = False

    context = {
        "message_data": message_data,
        "serials": serials,
        "current_serial": current_serial,
    }

    return render(request, "n5_lgr_backend/backend.html", context)
