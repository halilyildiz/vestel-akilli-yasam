# Gelişmiş servisler

[Ana sayfa](../README.tr.md) · [English](advanced.md)

Servisler: `vestel_appliances.apply`, `get_consumption`, `get_billing_settings`, `set_bill_limit`, `set_energy_price`, `set_subscriber_type`, `set_tariff_type` ve `set_energy_management`. Alanları Home Assistant eylem düzenleyicisinde görülebilir.

Örneklerdeki `YOUR_HA_DEVICE_ID` yerine eylem düzenleyicisinden seçtiğiniz **Home Assistant cihaz kayıt kimliğini** kullanın. Bu değer varlık kimliği, bulut UUID'si veya seri numarası değildir. Günlük kullanımda normal varlık kontrollerini tercih edin; gelişmiş `apply` anahtarları ve değerleri cihazınızın özellik tanımında bulunmalıdır.

Destekleyen bir buzdolabında ekran koruyucuyu kapatma örneği:

```yaml
action: vestel_appliances.apply
data:
  device_id: YOUR_HA_DEVICE_ID
  updates:
    - key: Refrigeration.Refrigerator.Setting.ScreenSaver
      value: 0
```

Bir çağrıda `updates` veya tam özellik tanımındaki `command` anahtarını kullanın; ikisini birlikte vermeyin. Ayar değerleri model tanımındaki tam sayılardır; ekranda görünen etiket veya ham register metni değildir. Çok ayarlı bir istekte sonraki yazım başarısız olursa önceki ayar uygulanmış olabilir. Tekrar denemeden önce cihazın gerçek durumunu kontrol edin.

Bir betikte üç aylık tahmini tüketimi okuma örneği:

```yaml
sequence:
  - action: vestel_appliances.get_consumption
    data:
      device_id: YOUR_HA_DEVICE_ID
      period: month
      count: 3
    response_variable: consumption
```

`period`: `day`, `week` veya `month`; `count`: 1–366. Yanıt, `estimated`, `period` ve tarihli `samples` alanlarını içerir. Eksik değerler sıfır sayılmaz. Salt okunur `get_consumption` ve `get_billing_settings` çağrılarında betik/otomasyon içinde bir yanıt değişkeni belirtin.

Seçilen cihazın bulunduğu **evin tamamı** için uygulamadaki tahmini fatura limitini değiştirme örneği:

```yaml
action: vestel_appliances.set_bill_limit
data:
  device_id: YOUR_HA_DEVICE_ID
  scope: home
  amount: 1000
  enabled: true
```

Varsayılan `scope: device` yalnızca seçilen cihazın limitini değiştirir. Tutar, uygulamanın fatura hesabında kullanılan 0–2147483647 aralığında bir tam sayıdır. Birim fiyat, abonelik türü, tarife ve enerji yönetimi servisleri de seçilen cihazın **evine** uygulanır. Bu servisler elektrik tedarikçisi sözleşmesini değiştirmez ve fiziksel elektrik kesme koruması sağlamaz.
