from django.db import models


class TestDevice(models.Model):
    serial = models.CharField(max_length=6, unique=True)

    def __str__(self):
        return self.serial

    def save(self, *args, **kwargs):
        existing_serial = TestDevice.objects.filter(serial=self.serial)
        if not existing_serial.exists():
            super().save(*args, **kwargs)


class TestSerialData(models.Model):
    device_serial = models.ForeignKey(TestDevice, on_delete=models.CASCADE)
    lgr_msg_ts = models.CharField(max_length=200)
    data_msg = models.CharField(max_length=2000)
    msg_type = models.CharField(max_length=200)
    flags = models.CharField(max_length=50)
    seq_num = models.IntegerField()
    msg_gen_ts = models.CharField(max_length=200)
    cell_id = models.CharField(max_length=200)
    cell_id_ts = models.CharField(max_length=200)
    actual_temp = models.CharField(max_length=5)
    trumi_st = models.CharField(max_length=200)
    trumi_st_upd_count = models.IntegerField()
    trumi_st_upd_ts = models.CharField(max_length=200)
    trumi_st_trans_count = models.CharField(max_length=50)
    reloc_st_trans_count = models.CharField(max_length=50)
    stored_st_trans_count = models.CharField(max_length=50)
    wifi_aps = models.CharField(max_length=50)
    pld_sz = models.CharField(max_length=50)
    pld_crc = models.CharField(max_length=10)
    buffer_link_type = models.CharField(max_length=50)
    header_crc = models.CharField(max_length=10)

    payload = models.CharField(max_length=8000)
    xyz_raw = models.CharField(max_length=8000)
    create_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Order the data by competition
        ordering = ("-create_at",)

    def __str__(self):
        return f"{self.device_serial} - {self.seq_num} - {self.lgr_msg_ts}"
