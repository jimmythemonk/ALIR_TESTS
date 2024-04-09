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

    context = {
        "message_data": message_data,
        "serials": serials,
        "current_serial": current_serial,
    }

    return render(request, "n5_lgr_backend/backend.html", context)
