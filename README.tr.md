# Vestel Smart Life — Home Assistant

Desteklenen **klima, kurutmalı çamaşır makinesi, bulaşık makinesi ve buzdolabınızı** Vestel Akıllı Yaşam hesabınızla Home Assistant'tan yönetin. Cihazın desteklediği kontrolleri, durumunu ve program ilerlemesini aynı yerde görün.

[**English**](README.md) · [Kurulum](#kurulum) · [Sorun giderme](docs/troubleshooting.tr.md) · [Güncelleme](docs/upgrading.tr.md)

[![Doğrulama](https://github.com/halilyildiz/vestel-akilli-yasam/actions/workflows/validate.yaml/badge.svg)](https://github.com/halilyildiz/vestel-akilli-yasam/actions/workflows/validate.yaml)
[![Marketplace'te aç](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=halilyildiz&repository=vestel-akilli-yasam&category=integration)

Resmî olmayan topluluk entegrasyonudur; Vestel tarafından geliştirilmez veya desteklenmez. **Vestel Akıllı Yaşam / Smart Life (homevsmart)** hesabına bağlanır; Tuya Smart Life için değildir.

[Mehmet Aktaş'ın MIT lisanslı Vestel Smart Home projesi](https://github.com/mehmetaktas/ha-vestel-smarthome) temel alınarak geliştirilmiştir. Kimlik doğrulama ve bulut iletişimi orijinal projeden uyarlanmış, ek cihaz aileleriyle genişletilmiştir. [Kaynak bildirimleri](NOTICE.md).

Bu sayfa `main` dalını anlatır; kurulu sürümünüz için [sürüm notlarını](https://github.com/halilyildiz/vestel-akilli-yasam/releases) kontrol edin. **Eski sürümü kullanıyorsanız yükseltmeden önce [geçiş rehberini](docs/upgrading.tr.md) okuyun**; özellikle seçenek adı veya fan modu kullanan otomasyonları gözden geçirin.

## Cihazım destekleniyor mu?

| Cihaz | Modele göre sunulan özellikler |
| --- | --- |
| Klima | Çalışma modu, hedef sıcaklık, fan, desteklenen ek özellikler ve zamanlayıcılar |
| Kurutmalı çamaşır makinesi | Program seçimi, yıkama/kurutma seçenekleri, başlatma/duraklatma ve ilerleme |
| Bulaşık makinesi | Program seçimi, seçenekler, başlatma/duraklatma/iptal ve ilerleme |
| Buzdolabı | Bölme sıcaklık hedefleri, desteklenen modlar, çocuk kilidi ve ekran koruyucu |

Cihazınız desteklenen Vestel uygulamasındaki hesabınızla önceden eşleştirilmiş olmalıdır. Yalnız yıkama yapan makineler, ayrı kurutucular, fırınlar ve diğer cihaz aileleri desteklenmez. Başka marka veya bölgede satılan Vestel üretimi bir ürün otomatik olarak uyumlu sayılmaz.

Kontroller cihazın buluttaki özellik tanımından oluşturulur. Model/firmware uyumluluk listesi henüz yayımlanmadığından tüm modeller için destek garantisi yoktur. Entegrasyon **internet bağlantısı gerektirir**; yalnızca yerel ağ üzerinden çalışmaz.

## Kurulum

Başlamadan önce **Home Assistant 2026.11.0 veya sonrası**, HACS ve Vestel uygulamasındaki e-posta/parolanız hazır olsun. Üretici gerektiriyorsa cihaz panelinden uzaktan kontrolü etkinleştirin.

1. **HACS**'ı (bazı kurulumlarda Marketplace) açın; menüsünden **Özel depolar** bölümüne girin.
2. Aşağıdaki adresi **Integration** türünde ekleyin:

   `https://github.com/halilyildiz/vestel-akilli-yasam`

3. **Vestel Smart Life** paketini bulup yükleyin; istenirse yeniden başlatın.
4. **Ayarlar → Cihazlar ve hizmetler → Entegrasyon ekle → Vestel Smart Life** yolunu izleyin.
5. Vestel hesabınızla giriş yapıp cihazlarınızın bulunduğu evi seçin.

Genel katalog kabulü tamamlanmadan da özel depo yöntemiyle kurulabilir. İngilizce ve Türkçe arayüz metinleri Home Assistant dil ayarına göre gösterilir.

[![Entegrasyon ekle](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=vestel_appliances)

**Elle kurulum:** `custom_components/vestel_appliances` klasörünün tamamını, lisans ve bildirim dosyalarıyla birlikte `<Home Assistant yapılandırma dizininiz>/custom_components/vestel_appliances` konumuna kopyalayın. Yeniden başlatıp 4–5. adımları izleyin.

## İlk kullanım

**Ayarlar → Cihazlar ve hizmetler → Vestel Smart Life** bölümünden bir cihazı açın. Cihaz sayfasında o modele ait kontrol ve durum varlıkları görünür. Bunları Home Assistant'ın kart düzenleyicisiyle panelinize ekleyebilirsiniz. Günlük kullanım için YAML gerekmez.

| Yapmak istediğiniz | Nereden başlamalısınız? |
| --- | --- |
| Klima sıcaklığını değiştirmek | Klima varlığını açıp desteklenen bir mod ve sıcaklık seçin. |
| Yıkama/bulaşık programı seçmek | Cihaz hazır ve uzaktan kontrol açıkken program seçimi varlığını kullanın. |
| Çalışan programı takip etmek | Çalışma durumu, seçili program ve kalan süre sensörlerini kullanın; bazı ayarlar çalışma sırasında kilitlenir. |
| Tüketim tahminlerini görmek | Cihazın varlık listesinde isteğe bağlı günlük/aylık tüketim varlıklarını etkinleştirin ve arka plan sorgusunu bekleyin. Bunlar tahmindir, sayaç ölçümü değildir. |

Seçilen uygulama evine eklenen desteklenen cihazlar, normalde yaklaşık 45 saniyede bir yapılan sonraki başarılı kontrolde görünür. Canlı bulut olayları da güncellemeyi tetikler. Cihaz kontrolleri enerji geçmişini beklemeden başlar.

## Bir şey çalışmıyorsa

- **Bağlantı kurulamıyor:** resmî uygulamayı ve interneti kontrol edin. Geçici bulut sorunları veya istek sınırları sonraki kontrolde düzelebilir.
- **Cihaz veya kontrol kullanılamıyor:** seçilen evi, panelin uzaktan kontrol iznini ve **Ayarlar → Sistem → Onarımlar** bölümünü kontrol edin.
- **Komut kabul edildi ancak doğrulanmadı:** yeniden denemeden önce cihazın gerçek durumuna ve resmî uygulamaya bakın; entegrasyon doğrulanmayan komutu otomatik tekrar göndermez.

Ayrıntılar [sorun giderme rehberinde](docs/troubleshooting.tr.md). Normal hataları [Issues](https://github.com/halilyildiz/vestel-akilli-yasam/issues) bölümüne kurulu entegrasyon/HA sürümü, cihaz modeli ve tekrar adımlarıyla bildirin. Entegrasyon menüsünden tanılama indirip **paylaşmadan önce inceleyin**.

## Gizlilik

E-posta, parola ve refresh token Home Assistant tarafından saklanır ve üreticinin bulutunda giriş için kullanılır. Yapılandırma dosyalarını ve yedekleri koruyun. Tanılama bilinen hassas bilgileri maskeler; yine de dosyayı gözden geçirin. Ayrıntılar için [gizlilik rehberine](docs/troubleshooting.tr.md), özel güvenlik bildirimi için [SECURITY.md](SECURITY.md) dosyasına bakın.

## Diğer rehberler

- [Gelişmiş servisler ve fatura ayarları](docs/advanced.tr.md)
- [Güncelleme, seçenek adı değişiklikleri ve diğer entegrasyonlardan geçiş](docs/upgrading.tr.md)
- [Geliştirme, testler ve güncelleme davranışı](docs/development.tr.md)
- [Sorun giderme, gizlilik ve kaldırma](docs/troubleshooting.tr.md)

## Lisans ve teşekkür

Kod [MIT lisansı](LICENSE) ile yayımlanır. **Mehmet Aktaş'ın** orijinal çalışmasına [NOTICE.md](NOTICE.md) içinde atıf yapılır ve [tam MIT bildirimi](licenses/ha-vestel-smarthome-MIT.txt) korunur. Kurulabilir klasörde [iki MIT bildirimi](custom_components/vestel_appliances/LICENSE) ve [NOTICE.md](custom_components/vestel_appliances/NOTICE.md) bulunur; yeniden dağıtımda bunları koruyun. Vestel görselleri ayrı hak sahiplerine aittir ve projenin MIT iznine dahil değildir.
