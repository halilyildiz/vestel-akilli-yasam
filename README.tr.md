# Vestel Akıllı Yaşam — Home Assistant

Vestel Akıllı Yaşam uygulamasına eklenmiş cihazlar için **resmî olmayan** bulut entegrasyonu. Vestel tarafından geliştirilmez veya desteklenmez.

Bu belge güncel `main` dalını anlatır. Bazı değişiklikler henüz yayımlanmış sürümde bulunmayabilir; kurulu sürümünüz için [sürüm notlarını](https://github.com/halilyildiz/vestel-akilli-yasam/releases) kontrol edin.

## Destek

Klima (**AC**), kurutmalı çamaşır makinesi (**WD**), bulaşık makinesi (**DW**) ve buzdolabı (**RF**) desteklenir. Kontroller cihazın servis tanımından oluşturulur. Aynı protokolü kullanmayan modeller, yalnız yıkama yapan makineler, ayrı kurutucular, fırınlar ve diğer ürün türleri için destek garantisi yoktur.

## Kurulum

Home Assistant 2026.11.0 veya sonrası ve uygulamada önceden eşleştirilmiş cihazlar gerekir.

1. HACS kurulu değilse önce HACS'ı kurun. HACS'ı (bazı kurulumlarda Marketplace adıyla görünür) açıp menüsündeki **Özel depolar** bölümünde aşağıdaki adresi **Integration** türünde ekleyin:
   `https://github.com/halilyildiz/vestel-akilli-yasam`
2. **Vestel Akıllı Yaşam** paketini yükleyin; istenirse yeniden başlatın.
3. Ayarlar → Cihazlar ve hizmetler → Entegrasyon ekle → **Vestel Akıllı Yaşam**.
4. Uygulamadaki e-posta ve şifrenizle giriş yapıp evinizi seçin.

Genel katalog kabulü tamamlanmadan da özel depo bağlantısıyla kurulabilir. Eski klima entegrasyonu veya keşif eklentisi gerekmez. Bu entegrasyonun elle kurulmuş bir sürümünden geçerken mevcut kaydı kaldırmayın: `vestel_appliances` alan adı ve varlık kimlikleri korunur.

Elle kurulumda `custom_components/vestel_appliances` klasörünü Home Assistant yapılandırma dizininizin `custom_components` klasörüne kopyalayıp yeniden başlatın. Ardından yukarıdaki entegrasyon ekleme adımlarını izleyin.

## Davranış

- Desteklenen yeni cihazlar, seçilen uygulama evine eklendikten sonraki başarılı sorguda bulunur; normal sorgu aralığı 45 saniyedir. Yeniden yükleme gerekmez.
- Canlı MQTT olayları buluttan güncel durum okunmasını tetikler; bağlantı kurulamazsa düzenli sorgulama devam eder.
- Cihaz kontrolleri ve canlı güncellemeler enerji geçmişini beklemeden başlar. Tüketim bilgileri arka planda alınır; ilk sorgu, entegrasyon kaldırılırken veya yeniden yüklenirken iptal edilir.
- Firmware/model değişiminde özellik tanımı yenilenir. Uyumsuz bir tanım diğer cihazları durdurmaz; Ayarlar → Sistem → Onarımlar altında bildirilir.
- Teknik tanılama ve günlük/aylık tahmini tüketim sensörleri varsayılan olarak kapalıdır. Tahminler gerçek sayaç ölçümü değildir.
- Seçili program sensörleri, seçim kontrolü çalışma sırasında kullanılamaz olduğunda programı göstermeye devam eder.
- Çalıştırma işlemleri cihaz panelindeki uzaktan kontrol iznine ve geçerli program durumuna bağlıdır. Geciken komut onayı otomatik tekrar gönderimine neden olmaz.
- Paylaşılan register'larda yalnızca hedeflenen bit alanları ve otomatik kapatılan uyumsuz seçenekler doğrulanır. Aynı register'daki başka bir ayarın değişmesi onayı engellemez.
- Geçici kimlik sunucusu hataları ve istek sınırları bağlantı hatası olarak ele alınır. Bozuk yanıtlar kayıtlı oturum bilgileri değiştirilmeden reddedilir. Gerçek hesap/token reddinde yeniden giriş istenebilir.
- Hesaptan kaldırılan cihazların kayıtları otomatik silinmez; varlıklar kullanılamaz olarak tutulur.

## Servis kullanımı

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

## Sınırlar ve sorun bildirimi

Entegrasyon internet ve Vestel/homevsmart bulutuna bağlıdır. Geliştiricinin bildirdiği dört fiziksel cihaz dışında model desteği doğrulanmış sayılmaz; model ve firmware bilgilerini içeren uyumluluk tablosu henüz yayımlanmamıştır.

| Belirti | Kontrol / çözüm |
| --- | --- |
| Bağlantı hatası, istek sınırı veya geçici sunucu sorunu | İnterneti ve resmî uygulamayı kontrol edin. Düzenli sorgunun yeniden denemesini bekleyin; art arda giriş denemeleri istek sınırını artırabilir. |
| Geçersiz hesap / yeniden giriş isteği | Hesabı resmî uygulamada doğrulayıp Home Assistant'ın yeniden giriş akışını tamamlayın. |
| Cihaz görünmüyor veya kullanılamıyor | Seçilen evi, desteklenen cihaz türünü, bağlantıyı ve paneldeki uzaktan kontrol iznini kontrol edin. Onarımlar bölümüne bakın. |
| Çalışırken bir seçenek kullanılamıyor | Program, aşama, mod veya uzaktan kontrol durumu değişikliği engelliyor olabilir. |
| Komut kabul edildi ancak doğrulanmadı | Yeniden denemeden önce cihazı ve resmî uygulamayı kontrol edin. Bu hataya otomatik tekrar döngüsü bağlamayın. |
| Tüketim sensörleri yok veya boş | İsteğe bağlı varlıkları varlık ayarlarından etkinleştirin ve arka plan sorgusunu bekleyin. Eksik tüketim verisi kontrol arızası anlamına gelmez. |

Hata bildiriminden önce uygulamadaki bağlantıyı ve panelin uzaktan kontrol iznini kontrol edin. Entegrasyon menüsünden maskelenmiş tanılama indirilebilir. Paylaşmadan önce dosyayı inceleyin; şifre, token, seri numarası veya MAC adresi paylaşmayın.

## Gizlilik ve güvenlik

Tanılama yalnızca seçilen teknik metadata alanlarını (model, firmware, cihaz türü ve bağlantı bilgileri), özellik tanımlarını, register durumlarını, uyumluluk sorunlarını ve komut doğrulama sonuçlarını içerir. Bilinmeyen metadata alanları alınmaz. Bilinen hassas alanlar ve başka metinlerde tekrarlanan değerler, iç içe veriler ve gömülü JSON dahil maskelenir. Yeni bulut alanları kişisel bilgi içerebileceğinden paylaşmadan önce dosyayı yine de inceleyin.

E-posta, parola ve refresh token Home Assistant'ın yapılandırma kaydında saklanır. Token yenilemesi reddedildiğinde giriş yapılabilmesi için parola tutulur; entegrasyona özel ek bir şifreleme katmanı yoktur. Yapılandırma dosyalarını ve yedekleri kimlik bilgisi içeriyor gibi koruyun. Tanılama, bilinen kimlik bilgilerini maskeleme için kullanır; yapılandırma kaydını dışarı aktarmaz.

Kimlik bilgileri bu depoya veya geliştiriciye gönderilmez; giriş işlemi bulut sağlayıcısına yapılır. Güvenlik açığı bildirim yöntemi için [SECURITY.md](SECURITY.md) dosyasına bakın. Hassas bilgi içermeyen normal hatalar [Issues](https://github.com/halilyildiz/vestel-akilli-yasam/issues) bölümünden bildirilebilir.

## Geliştirme ve doğrulama

```sh
python -m unittest discover -s tests -v
```

Güncel çevrimdışı test kümesi 145 test içerir. Protokol sınırları, oturum hataları, yanıt doğrulama, komut geri okuması, arka plan başlangıcı, enerji hatalarının ayrılması ve tanılama maskelemesi test edilir. Verilerde sentetik cihaz bilgileri kullanılır; gerçek cihaza veya buluta çağrı yapılmaz. Home Assistant sınıflarının çoğu taklittir; bu testler gerçek Home Assistant veya tüm fiziksel modellerin doğrulaması değildir.

GitHub Actions çevrimdışı testleri, hassfest ve HACS doğrulamasını çalıştırır. Kontrollerin geçmesi, HACS genel kataloğuna kabul edildiği anlamına gelmez.

## Kaldırma

Önce Ayarlar → Cihazlar ve hizmetler bölümünden entegrasyon kaydını kaldırın. Ardından HACS/Marketplace üzerinden paketi kaldırıp istenirse yeniden başlatın. Kaydın kaldırılması Home Assistant varlıklarını da kaldırır; bunlara bağlı otomasyonları güncellemeniz gerekir. Resmî uygulamadaki cihaz eşleştirmeleri ayrı tutulur.

## Lisans

Kod [MIT lisansı](LICENSE) ile yayımlanır. Üçüncü taraf kaynaklar ve Vestel uygulama görsellerinin ayrı durumu için [NOTICE.md](NOTICE.md) dosyasına bakın.
