# Güncelleme ve geçiş

[Ana sayfa](../README.tr.md) · [English](upgrading.md)

Entegrasyonun görünen adı **Vestel Smart Life** oldu. Bağlanılan uygulama/hesap **Vestel Akıllı Yaşam / Smart Life (homevsmart)** olarak kalır; bu entegrasyon **Tuya Smart Life için değildir**. Yurt dışında veya farklı markalarla satılan Vestel üretimi cihazların çalışması, aynı desteklenen hesabı, bulutu ve protokolü kullanmasına bağlıdır. Diğer hesap bölgeleri ve modeller ayrıca doğrulanmalıdır.

Kaynak dil İngilizcedir. Kurulum, varlık adları, seçenek/durum etiketleri, servis açıklamaları ve kullanıcıya gösterilen hatalar için Türkçe çeviriler bulunur. Görünen dil Home Assistant dil ayarlarına göre belirlenir. Yeni model alanları gerektiğinde okunabilir teknik adlarla gösterilir.

`vestel_appliances` alanı, benzersiz kimlikler ve mevcut varlık kayıtları korunur. Varsayılan entegrasyon kayıt adı güncellenir; kullanıcının verdiği özel kayıt adı korunur. Mevcut varlık kimlikleri yeniden adlandırılmaz. Mevcut depo adresi `halilyildiz/vestel-akilli-yasam` olarak kalır. Depo adının değiştirilmesi planlanıyor; işlem tamamlanana kadar kurulum rehberindeki çalışan adresi kullanın.

**Otomasyon geçişi:** seçim seçenekleri, enum sensör durumları ve klima fan modları artık çevrilmiş metin yerine sabit makine anahtarları kullanır. Arayüz bu anahtarları seçili dilde gösterir. Yükseltmeden önce düz metin durum karşılaştıran veya seçenek/fan modu metni gönderen otomasyon, betik, şablon ve panelleri kontrol edin. Gerçek değeri Geliştirici Araçları → Durumlar bölümünden alın; çevrilmiş ekran etiketini kopyalamayın.

| Önceki değer | Makine anahtarı | İngilizce görünüm | Türkçe görünüm |
| --- | --- | --- | --- |
| `Ekonomi` | `eco` | Economy | Ekonomi |
| `Pamuklu` | `cotton` | Cotton | Pamuklu |
| `Soğutma` | `cooling` | Cooling | Soğutma |
| `Auto` (klima fan modu) | `auto` | Automatic | Otomatik |

Gelişmiş `vestel_appliances.apply` çağrısındaki `updates[].value` alanı üreticinin tam sayı kodunu kullanmaya devam eder; bu alana makine anahtarı yazmayın. Yükseltme öncesi ve sonrasındaki durum geçmişinde eski metinler ve yeni anahtarlar birlikte bulunabilir.

## Bu entegrasyonu güncelleme

Yükseltmeden önce Home Assistant yedeği alın. Paketi HACS üzerinden güncelleyin ve yeniden başlatma istemini izleyin. Mevcut `vestel_appliances` kaydını koruyun; kaldırıp yeniden eklemeniz gerekmez. Elle kurulumda `custom_components/vestel_appliances` klasörünün içeriğini, `LICENSE` ve `NOTICE.md` dahil yeni sürümle değiştirip yeniden başlatın.

Düz metin seçenek/enum/fan durumu kullanan betik ve otomasyonları yukarıdaki tabloya göre inceleyin. Varlık kimliklerinin korunması eski seçenek metinlerinin de korunacağı anlamına gelmez. Etkilenen otomasyonları kullanmadan önce kontrol edin. Geri dönmeniz gerekirse önceki paket sürümünüzü ve yapılandırma yedeğinizi geri yükleyin; entegrasyon otomasyonları veya kayıtlı durum geçmişini otomatik dönüştürmez.

## Mehmet Aktaş'ın entegrasyonundan geçiş

Orijinal entegrasyon `vestel_smarthome`, bu proje `vestel_appliances` alanını kullanır. Bunlar ayrı entegrasyonlardır. Bu projeyi kurmak orijinal yapılandırma kaydını, varlık kimliklerini, panelleri veya otomasyonları otomatik taşımaz.

Eski varlık kimliklerini ve bunları kullanan otomasyonları not edin. Bu entegrasyonu kurup giriş yapın, aynı evi seçin, yeni varlıkları kontrol edin ve bağlantıları güncelleyin. Geçiş sırasında aynı cihazı yöneten mükerrer otomasyonları etkin bırakmayın. Eski kaydı yalnızca yeni kurulumun çalıştığını doğruladıktan sonra kaldırın. Resmî uygulamadaki cihaz eşleştirmeleri Home Assistant kayıtlarından ayrıdır.
