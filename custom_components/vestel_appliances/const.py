DOMAIN = "vestel_appliances"
APP_NAME = "Vestel Akıllı Yaşam"
SUPPORTED_TYPES = {"AC", "WD", "DW", "RF"}
SCAN_SECONDS = 45

LABELS = {
    "Mode": "Çalışma modu", "Temperature": "Sıcaklık", "Speed": "Fan hızı",
    "Turbo": "Turbo", "SleepMode": "Uyku", "Ionizer": "İyonizer", "Eco": "Ekonomi",
    "HorizontalSwing": "Yatay kanat", "VerticalSwing": "Dikey kanat",
    "SpinSpeed": "Sıkma hızı", "Dry": "Kurutma seviyesi", "TimeDry": "Kurutma süresi",
    "Delay": "Gecikmeli başlatma", "DelayTimer": "Gecikmeli başlatma",
    "Tablet": "Tablet deterjan", "UpperSpray": "Üst sepet", "LowerSpray": "Alt sepet",
    "ExtraDry": "Ekstra kurutma", "ExtraHygiene": "Ekstra hijyen", "ExtraRinse": "Ekstra durulama",
    "ScreenSaver": "Ekran koruyucu", "ChildLock": "Çocuk kilidi",
    "Start": "Başlat", "Pause": "Duraklat", "Cancel": "İptal",
    "PreProgram": "Program seçimine dön", "Selection": "Program seçimine dön",
    "InDelay": "Gecikmeyi başlat", "IonizerInProgress": "İyonizeri başlat",
    "PowerOff": "Kapat", "RoomTemperature": "Oda sıcaklığı",
    "ExecutionState": "Çalışma durumu", "StepInfo": "Program aşaması",
    "ProgramPhase": "Program aşaması", "SelectedProgram": "Seçili program",
    "RemainingDuration": "Kalan süre", "RemainingDelayDuration": "Kalan gecikme",
    "ProgramDuration": "Program süresi", "Duration": "Program süresi",
    "RemoteControl": "Uzaktan kontrol", "RemoteControlOn": "Uzaktan kontrol",
    "DoorOpen": "Kapak açık", "EnergyOn": "Güç açık", "ChildLockOn": "Çocuk kilidi",
    "Standby": "Bekleme", "Warning": "Uyarı", "SaltAndRinseAid": "Tuz ve parlatıcı",
    "UvonOn": "UV aç", "UvonOff": "UV kapat", "SettingIndex": "UV ayar durumu",
}

CHOICES = {
    "UvonOn": "UV açık", "UvonOff": "UV kapalı",
    "Auto": "Otomatik", "Cooling": "Soğutma", "Heating": "Isıtma",
    "Dehumidifying": "Nem alma", "Ventilating": "Fan", "PowerOff": "Kapalı",
    "Normal": "Normal", "SuperFreeze": "Hızlı dondurma", "SuperCooler": "Hızlı soğutma",
    "Holiday": "Tatil", "Eco": "Ekonomi", "NoSpin": "Sıkma yok", "ColdDegree": "Soğuk",
    "NoLevel": "Kurutma yok", "Level1": "Seviye 1", "Level2": "Seviye 2", "Level3": "Seviye 3",
    "NoTime": "Süreli kurutma yok", "Off": "Kapalı",
    "Eco4060": "Eko 40–60", "Cotton": "Pamuklu", "Cotton20": "Pamuklu hızlı 20 °C",
    "Synthetics": "Sentetikler", "WoolSilk": "Yünlü", "Duvet": "Yorgan",
    "Rinse": "Durulama", "AllergySafe": "Alerji uzmanı", "SpinDrain": "Sıkma / tahliye",
    "Rapid1512": "Hızlı", "Fast60": "Hızlı 60 dk", "DryDelicate": "Hassas kurutma",
    "DryCotton": "Pamuklu kurutma", "DryJetWash": "Hızlı yıka ve kurut",
    "DryCotton6Wash": "Pamuklu yıka ve kurut", "Prewash": "Ön yıkama",
    "Quick30": "Hızlı 30 dk", "Eco50": "Eko 50 °C", "Easycare": "Pratik 60 °C",
    "Super50": "Süper 50 dk", "Smart3050": "Cam ve bardak yıkama",
    "Smart5060": "Oto akıllı", "Smart6070": "Oto yoğun", "Favorite1": "Favori",
}


def label(key):
    if ".Cooler.Temperature" in key:
        return "Soğutucu sıcaklık ayarı"
    if ".Freezer.Temperature" in key:
        return "Dondurucu sıcaklık ayarı"
    return LABELS.get(key.rsplit(".", 1)[-1], key.split(".", 2)[-1])


def choice(key):
    short = key.rsplit(".", 1)[-1]
    if short.endswith("Degree") and short[:-6].isdigit():
        return short[:-6] + " °C"
    if short.endswith("Rpm"):
        return short[:-3] + " dev/dk"
    if short.startswith("Time") and short.endswith("min"):
        return short[4:-3] + " dk"
    if short.startswith("Speed") and short[5:].isdigit():
        return "Kademe " + short[5:]
    if short.startswith("Pos"):
        return "Salınım" if short == "Pos6" else "Konum " + short[3:]
    if short.endswith("C") and short[:-1].isdigit():
        return short[:-1] + " °C"
    if short.startswith("M") and short[1:].isdigit():
        return "−" + short[1:] + " °C"
    return CHOICES.get(short, short)
