import uuid
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import send_mail
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import Paper, AnonymizedPaper, PaperLog, AnonymizedContent, RestoredPaper
from reviews.models import Review, Message
from users.models import User
from .pdf_service import PDFAnonymizer
import json
import os
import fitz
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

@csrf_exempt
@api_view(['POST'])
def upload_paper(request):
    if 'file' not in request.FILES:
        return Response({'error': 'PDF dosyası gerekli'}, status=status.HTTP_400_BAD_REQUEST)

    email = request.data.get('email', '')
    if not email:
        return Response({'error': 'E-posta adresi gerekli'}, status=status.HTTP_400_BAD_REQUEST)

    file = request.FILES['file']
    # PDF formatı kontrolü
    if not file.name.endswith('.pdf'):
        return Response({'error': 'Sadece PDF dosyaları kabul edilmektedir'}, status=status.HTTP_400_BAD_REQUEST)

    # Makale oluştur
    paper = Paper.objects.create(
        email=email,
        original_file=file
    )

    # Log kaydı ekle
    PaperLog.objects.create(
        paper=paper,
        action="Makale yüklendi",
        details=f"Yükleme e-posta: {email}"
    )

    # Makale durumunu işleniyor olarak güncelle
    paper.status = 'processing'
    paper.save()

    # Yazar ve kurum tespiti yap, ama anonimleştirme yapma
    try:
        # PDF'den metadataları çıkar
        pdf_analyzer = PDFAnonymizer(paper.original_file.path)
        
        # Yazarları ve kurumları algıla
        authors = pdf_analyzer.detect_authors()
        institutions = pdf_analyzer.detect_institutions()
        
        # Tespit edilen verileri Paper modeline kaydet
        paper.set_detected_authors(authors)
        paper.set_detected_institutions(institutions)
        
        # Log kaydı ekle
        PaperLog.objects.create(
            paper=paper,
            action="Yazarlar ve kurumlar tespit edildi",
            details=f"Tespit edilen yazarlar: {', '.join(authors)}, Kurumlar: {', '.join(institutions)}"
        )
        
        # Makale durumunu güncelle - submitted olarak ayarla
        paper.status = 'submitted'
        paper.save()
    except Exception as e:
        # Hata durumunda log kaydı ekle
        PaperLog.objects.create(
            paper=paper,
            action="Yazar ve kurum tespiti hatası",
            details=f"Hata: {str(e)}"
        )
        print(f"Tespit hatası: {e}")

    # E-posta gönder
    send_mail(
        'Makale Yükleme Başarılı',
        f'Makaleniz başarıyla yüklendi. Takip numaranız: {paper.tracking_id}',
        'noreply@makalesistemi.com',
        [email],
        fail_silently=False,
    )

    return Response({
        'tracking_id': paper.tracking_id,
        'message': 'Makale başarıyla yüklendi'
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
def paper_status(request, tracking_id):
    try:
        paper = Paper.objects.get(tracking_id=tracking_id)
        email = request.GET.get('email', '')

        if paper.email != email:
            return Response({'error': 'Yetkilendirme hatası'}, status=status.HTTP_403_FORBIDDEN)

        # Log kayıtlarını al ama anonimleştirme loglarını tamamen çıkar
        logs = []
        for log in paper.logs.all().values('action', 'timestamp', 'details'):
            # Anonimleştirme veya yazar/kurum tespiti ile ilgili logları tamamen atla
            if 'anonimleştiril' in log['action'] or 'Yazarlar ve kurumlar tespit edildi' in log['action']:
                continue
            logs.append(log)
            
        # Makale statüsü revision, accepted veya rejected ise değerlendirme bilgileri de ekle
        review_data = None
        if paper.status in ['revision', 'accepted', 'rejected'] and paper.reviews.filter(status='completed').exists():
            review = paper.reviews.filter(status='completed').first()
            
            # Şifresi çözülmüş combined dosya varsa onu kullan, yoksa normal review dosyasını kullan
            review_file_url = None
            if review.combined_review_file:
                review_file_url = review.combined_review_file.url
            elif review.review_file:
                review_file_url = review.review_file.url
                
            review_data = {
                'recommendation': review.recommendation,
                'comments': review.comments,
                'review_file_url': review_file_url
            }

        return Response({
            'tracking_id': paper.tracking_id,
            'status': paper.status,
            'title': paper.title,
            'submitted_at': paper.submitted_at,
            'updated_at': paper.updated_at,
            'logs': logs,
            'review': review_data
        })
    except Paper.DoesNotExist:
        return Response({'error': 'Makale bulunamadı'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
def paper_list(request):
    # Editör yetkilendirmesi
    is_editor = request.GET.get('is_editor', 'false').lower() == 'true'

    if not is_editor:
        return Response({'error': 'Yetkilendirme hatası'}, status=status.HTTP_403_FORBIDDEN)

    # Alana göre filtreleme
    field = request.GET.get('field', '')
    if field:
        papers = Paper.objects.filter(field=field).order_by('-submitted_at')
    else:
        papers = Paper.objects.all().order_by('-submitted_at')

    paper_list = []
    for paper in papers:
        paper_info = {
            'tracking_id': paper.tracking_id,
            'title': paper.title or f"Paper {paper.tracking_id}",
            'status': paper.status,
            'field': paper.field,  # Alan bilgisini ekle
            'field_display': dict(Paper.FIELD_CHOICES).get(paper.field, 'Not Selected'),  # Görüntüleme için alan adı
            'submitted_at': paper.submitted_at,
            'is_anonymized': hasattr(paper, 'anonymized'),
            'has_reviewer': paper.reviews.exists(),
        }
        paper_list.append(paper_info)

    return Response(paper_list)


@api_view(['GET'])
def paper_detail(request, tracking_id):
    # Editör veya yazar yetkilendirmesi
    is_editor = request.GET.get('is_editor', 'false').lower() == 'true'
    email = request.GET.get('email', '')

    try:
        paper = Paper.objects.get(tracking_id=tracking_id)

        if not is_editor and paper.email != email:
            return Response({'error': 'Yetkilendirme hatası'}, status=status.HTTP_403_FORBIDDEN)

        # Tespit edilen yazarları ve kurumları al
        authors = paper.get_detected_authors()
        institutions = paper.get_detected_institutions()

        # Log kayıtları
        logs = list(paper.logs.all().values('action', 'timestamp', 'details'))
        
        # Anonimleştirme durumunu ve anonimleştirilmiş öğeleri kontrol et
        is_anonymized = hasattr(paper, 'anonymized')
        anonymized_items_list = []
        if is_anonymized:
            # İlişkili AnonymizedContent nesnelerini al
            try:
                anonymized_contents = paper.anonymized.anonymized_contents.all()
                anonymized_items_list = [content.original_text for content in anonymized_contents]
            except AttributeError: # Henüz AnonymizedPaper yoksa (olmamalı ama kontrol edelim)
                is_anonymized = False # Durumu false yap
        
        # PDF'de bulanıklaştırılabilir görsellerin olup olmadığını kontrol et
        has_blurrable_images = False
        if is_editor and not is_anonymized:
            try:
                pdf_anonymizer = PDFAnonymizer(paper.original_file.path)
                has_blurrable_images = pdf_anonymizer.has_blurrable_images()
            except Exception as e:
                print(f"Bulanıklaştırılabilir görselleri kontrol ederken hata oluştu: {e}")

        response_data = {
            'tracking_id': paper.tracking_id,
            'email': paper.email if is_editor else None,
            'title': paper.title,
            'status': paper.status,
            'submitted_at': paper.submitted_at,
            'updated_at': paper.updated_at,
            'is_anonymized': is_anonymized, # Hesaplanan değeri kullan
            'logs': logs,
        }

        if is_editor:
            response_data.update({
                'authors': authors,
                'institutions': institutions,
                'keywords': paper.keywords,
                'field': paper.field, # Alan bilgisini ekle
                'anonymized_file_url': paper.anonymized.file.url if is_anonymized else None, # Hesaplanan değeri kullan
                'anonymized_items': anonymized_items_list, # Yeni listeyi ekle
                'has_blurrable_images': has_blurrable_images # Bulanıklaştırılabilir görsel var mı bilgisi
            })

        return Response(response_data)

    except Paper.DoesNotExist:
        return Response({'error': 'Makale bulunamadı'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': f'Makale detayı alınırken hata oluştu: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def anonymize_paper(request, tracking_id):
    """
    Bir makaleyi anonimleştirir ve şifreli verileri kaydeder.
    Editör tarafından geri dönüştürülebilir bir şekilde şifreleme kullanır.
    """
    # Editör yetkilendirmesi
    is_editor = request.GET.get('is_editor', 'false').lower() == 'true'

    if not is_editor:
        return Response({'error': 'Yetkilendirme hatası'}, status=status.HTTP_403_FORBIDDEN)

    try:
        paper = Paper.objects.get(tracking_id=tracking_id)

        # Daha önce anonimleştirilmiş mi kontrol et
        if hasattr(paper, 'anonymized'):
            return Response({'error': 'Bu makale zaten anonimleştirilmiş'}, status=status.HTTP_400_BAD_REQUEST)

        # Anonimleştirilecek alanları al
        authors_to_anonymize = request.data.get('authors', [])
        institutions_to_anonymize = request.data.get('institutions', [])
        
        # Görsel bulanıklaştırma seçeneklerini al
        blur_images = request.data.get('blur_images', True)
        blur_factor = request.data.get('blur_factor', 5)
        
        # Gerekirse integer'a dönüştür
        if isinstance(blur_factor, str):
            try:
                blur_factor = int(blur_factor)
            except ValueError:
                blur_factor = 5

        # PDF'i anonimleştir
        pdf_anonymizer = PDFAnonymizer(paper.original_file.path)
        
        # Anonimleştirme işlemini gerçekleştir - şimdi şifrelemeyi de yapıyor
        anonymized_path, encryption_key, anonymized_content = pdf_anonymizer.anonymize_pdf(
            authors_to_anonymize=authors_to_anonymize,
            institutions_to_anonymize=institutions_to_anonymize,
            blur_images=blur_images,
            blur_factor=blur_factor
        )

        if not anonymized_path or not encryption_key or not anonymized_content:
            return Response({'error': 'Anonimleştirme işlemi başarısız oldu'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Anonimleştirilmiş PDF'i kaydet
        anonymized_paper = AnonymizedPaper.objects.create(
            paper=paper,
            file=os.path.basename(anonymized_path),
            encryption_key=encryption_key,
            encryption_method="AES"
        )
        
        # Anonimleştirilen içerikleri veritabanına kaydet
        for content in anonymized_content:
            # İçerik özelliklerini çıkar
            page_num = content.get("page")
            rect = content.get("rect")
            replacement_text = content.get("replacement_text")
            original_text = content.get("original_text")
            encrypted_text = content.get("encrypted_text")
            content_type = content.get("content_type")
            
            # AnonymizedContent nesnesini oluştur
            anonymized_item = AnonymizedContent(
                anonymized_paper=anonymized_paper,
                replacement_text=replacement_text,
                original_text=original_text,
                encrypted_text=encrypted_text,
                content_type=content_type,
                page_number=page_num
            )
            
            # Konum bilgisini JSON olarak kaydet
            if rect:
                position_data = {
                    "x0": rect.x0,
                    "y0": rect.y0,
                    "x1": rect.x1,
                    "y1": rect.y1
                }
                anonymized_item.set_position(position_data)
                
            anonymized_item.save()

        # Log kaydı ekle
        log_details = f"Anonimleştirilen yazarlar: {', '.join(authors_to_anonymize)}, Kurumlar: {', '.join(institutions_to_anonymize)}"
        if blur_images:
            log_details += f", Referans bölümünden sonraki görseller bulanıklaştırıldı (faktör: {blur_factor})"
            
        PaperLog.objects.create(
            paper=paper,
            action="Makale şifreli şekilde anonimleştirildi",
            details=log_details
        )

        # Makale durumunu güncelle
        paper.status = 'reviewing'
        paper.save()

        return Response({'message': 'Makale başarıyla anonimleştirildi ve şifrelendi'})

    except Paper.DoesNotExist:
        return Response({'error': 'Makale bulunamadı'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': f'Anonimleştirme hatası: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def assign_reviewer(request, tracking_id):
    # Editör yetkilendirmesi
    is_editor = request.GET.get('is_editor', 'false').lower() == 'true'

    if not is_editor:
        return Response({'error': 'Yetkilendirme hatası'}, status=status.HTTP_403_FORBIDDEN)

    try:
        paper = Paper.objects.get(tracking_id=tracking_id)

        # Anonimleştirilmiş mi kontrol et
        if not hasattr(paper, 'anonymized'):
            return Response({'error': 'Makale henüz anonimleştirilmemiş'}, status=status.HTTP_400_BAD_REQUEST)

        # Zaten hakem atanmış mı kontrol et
        if paper.reviews.exists():
            return Response({'error': 'Bu makaleye zaten bir hakem atanmış'}, status=status.HTTP_400_BAD_REQUEST)

        reviewer_email = request.data.get('reviewer_email', '')
        if not reviewer_email:
            return Response({'error': 'Hakem e-posta adresi gerekli'}, status=status.HTTP_400_BAD_REQUEST)

        # Hakem kullanıcısını bul veya oluştur
        reviewer, created = User.objects.get_or_create(
            email=reviewer_email,
            defaults={'is_reviewer': True}
        )

        # Değerlendirme kaydı oluştur - explisit olarak None değerleri atanmalı
        review = Review(
            paper=paper,
            reviewer=reviewer,
            status='assigned',
            comments='',  # Boş string olarak başlat
            recommendation=None  # Açıkça None olarak ayarla
        )
        review.save()

        # Makale durumunu güncelle
        paper.status = 'reviewing'
        paper.save()

        # Log kaydı ekle
        PaperLog.objects.create(
            paper=paper,
            action="Hakem atandı",
            details=f"Hakem: {reviewer_email}"
        )

        # Hakeme e-posta gönder
        send_mail(
            'Değerlendirme Davetiyesi',
            f'Bir makale değerlendirmeniz için atandı. Lütfen sisteme giriş yaparak değerlendirmenizi tamamlayın.\n\n' +
            f'Makale ID: {paper.tracking_id}',
            'noreply@makalesistemi.com',
            [reviewer_email],
            fail_silently=False,
        )

        return Response({
            'message': 'Hakem başarıyla atandı',
            'reviewer_email': reviewer_email,
            'review_status': 'assigned'
        })

    except Paper.DoesNotExist:
        return Response({'error': 'Makale bulunamadı'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': f'Hakem atama hatası: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'POST'])
def paper_messages(request, tracking_id):
    try:
        paper = Paper.objects.get(tracking_id=tracking_id)

        # Yetkilendirme kontrolü
        is_editor = request.GET.get('is_editor', 'false').lower() == 'true'
        email = request.GET.get('email', '')

        if not is_editor and paper.email != email:
            return Response({'error': 'Yetkilendirme hatası'}, status=status.HTTP_403_FORBIDDEN)

        if request.method == 'GET':
            # Mesajları listele
            messages = paper.messages.all().values('sender_email', 'is_editor', 'content', 'created_at')
            return Response(list(messages))

        elif request.method == 'POST':
            # Yeni mesaj ekle
            content = request.data.get('content', '')
            if not content:
                return Response({'error': 'Mesaj içeriği gerekli'}, status=status.HTTP_400_BAD_REQUEST)

            message = Message.objects.create(
                paper=paper,
                sender_email=email if not is_editor else 'editor@makalesistemi.com',
                is_editor=is_editor,
                content=content
            )

            # Log kaydı ekle
            PaperLog.objects.create(
                paper=paper,
                action="Mesaj gönderildi",
                details=f"Gönderen: {'Editör' if is_editor else email}"
            )

            return Response({'message': 'Mesaj başarıyla gönderildi'})

    except Paper.DoesNotExist:
        return Response({'error': 'Makale bulunamadı'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
def sync_files(request, tracking_id):
    """Dosya sistemi ile veritabanı kayıtlarını senkronize eder"""
    # Editör yetkilendirmesi
    is_editor = request.GET.get('is_editor', 'false').lower() == 'true'
    if not is_editor:
        return Response({'error': 'Yetkilendirme hatası'}, status=status.HTTP_403_FORBIDDEN)

    try:
        paper = Paper.objects.get(tracking_id=tracking_id)
        result = {'action': 'none', 'details': 'Dosya kontrolü tamamlandı, değişiklik yapılmadı'}
        
        # Orijinal PDF'in varlığını kontrol et
        if not os.path.exists(paper.original_file.path):
            # Log kaydı ekle
            PaperLog.objects.create(
                paper=paper,
                action="Dosya silinmiş",
                details=f"Orijinal PDF dosyası sistemde bulunamadı: {paper.original_file.path}"
            )
            # Makaleyi sil
            paper_id = paper.tracking_id
            paper.delete()
            result = {'action': 'deleted', 'details': f'Makale silindi çünkü orijinal PDF bulunamadı: {paper_id}'}
            return Response(result)
        
        # Anonimleştirilmiş PDF'in varlığını kontrol et
        if hasattr(paper, 'anonymized'):
            anonymized_paper = paper.anonymized
            try:
                anonymized_path = anonymized_paper.file.path
                if not os.path.exists(anonymized_path):
                    # Anonimleştirme kaydını sil
                    anonymized_paper.delete()
                    # Log kaydı ekle
                    PaperLog.objects.create(
                        paper=paper,
                        action="Anonimleştirme kaydı silindi",
                        details=f"Anonimleştirilmiş PDF dosyası sistemde bulunamadı: {anonymized_path}"
                    )
                    # Makale durumunu güncelle
                    paper.status = 'submitted'
                    paper.save()
                    result = {'action': 'anonymized_deleted', 'details': f'Anonimleştirme kaydı silindi çünkü PDF bulunamadı: {anonymized_path}'}
            except Exception as e:
                # Dosya yolu alınamadı
                result = {'action': 'error', 'details': f'Dosya yolu alınırken hata: {str(e)}'}
        
        return Response(result)

    except Paper.DoesNotExist:
        return Response({'error': 'Makale bulunamadı'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({'error': f'Dosya senkronizasyonu sırasında hata: {str(e)}'}, 
                      status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def review_status(request, tracking_id):
    """Makalenin değerlendirme durumunu döndürür"""
    # Editör yetkilendirmesi
    is_editor = request.GET.get('is_editor', 'false').lower() == 'true'
    if not is_editor:
        return Response({'error': 'Yetkilendirme hatası'}, status=status.HTTP_403_FORBIDDEN)

    try:
        paper = Paper.objects.get(tracking_id=tracking_id)
        review = paper.reviews.first()  # İlk değerlendirmeyi al

        if review:
            response_data = {
                'reviewer_email': review.reviewer.email,
                'status': review.status,
                'is_completed': review.status == 'completed',
                'recommendation': review.recommendation,
                'comments': review.comments,
                'review_file': review.review_file.url if review.review_file else None
            }
        else:
            response_data = {
                'reviewer_email': None,
                'status': None,
                'is_completed': False,
                'recommendation': None,
                'comments': None,
                'review_file': None
            }

        return Response(response_data)

    except Paper.DoesNotExist:
        return Response({'error': 'Makale bulunamadı'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': f'Değerlendirme durumu alınırken hata oluştu: {str(e)}'}, 
                       status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def restore_original_paper(request, tracking_id):
    """
    Anonimleştirilmiş bir makaleyi orijinal haline geri döndürür.
    Editör tarafından yapılması gereklidir.
    """
    # Editör yetkilendirmesi
    is_editor = request.GET.get('is_editor', 'false').lower() == 'true'

    if not is_editor:
        return Response({'error': 'Yetkilendirme hatası'}, status=status.HTTP_403_FORBIDDEN)

    try:
        paper = Paper.objects.get(tracking_id=tracking_id)

        # Anonimleştirilmiş mi kontrol et
        if not hasattr(paper, 'anonymized'):
            return Response({'error': 'Bu makale henüz anonimleştirilmemiş'}, status=status.HTTP_400_BAD_REQUEST)
            
        # Zaten geri yüklenmiş mi kontrol et
        if hasattr(paper, 'restored'):
            return Response({'error': 'Bu makale zaten orijinal haline geri yüklenmiş'}, status=status.HTTP_400_BAD_REQUEST)
        
        anonymized_paper = paper.anonymized
        
        # Şifreli içerikleri al
        anonymized_contents = anonymized_paper.anonymized_contents.all()
        
        if not anonymized_contents.exists():
            return Response({'error': 'Anonimleştirilmiş içerik bulunamadı'}, status=status.HTTP_400_BAD_REQUEST)
            
        # Şifreleme anahtarını al
        encryption_key = anonymized_paper.encryption_key
        
        if not encryption_key:
            return Response({'error': 'Şifreleme anahtarı bulunamadı'}, status=status.HTTP_400_BAD_REQUEST)
            
        # Anonimleştirilmiş PDF'in yolunu al
        anonymized_pdf_path = anonymized_paper.file.path
        
        # Geri yükleme işlemi için içerik verilerini hazırla
        content_data = []
        for content in anonymized_contents:
            position = content.get_position()
            content_item = {
                "page": content.page_number,
                "rect": fitz.Rect(position["x0"], position["y0"], position["x1"], position["y1"]) if position else None,
                "replacement_text": content.replacement_text,
                "encrypted_text": content.encrypted_text
            }
            content_data.append(content_item)
            
        # Orijinal haline geri döndür
        restored_path = PDFAnonymizer.restore_original_pdf(
            anonymized_pdf_path, 
            content_data, 
            encryption_key
        )
        
        if not restored_path:
            return Response({'error': 'Geri yükleme işlemi başarısız oldu'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        # Geri yüklenmiş PDF'i kaydet
        restored_paper = RestoredPaper.objects.create(
            paper=paper,
            anonymized_paper=anonymized_paper,
            file=os.path.basename(restored_path)
        )
        
        # Log kaydı ekle
        PaperLog.objects.create(
            paper=paper,
            action="Makale orijinal haline geri yüklendi",
            details="Anonimleştirilmiş içerik şifre çözülerek orijinal haline getirildi"
        )
        
        return Response({
            'message': 'Makale başarıyla orijinal haline geri yüklendi',
            'restored_file_url': restored_paper.file.url
        })
        
    except Paper.DoesNotExist:
        return Response({'error': 'Makale bulunamadı'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': f'Geri yükleme hatası: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def update_keywords(request, tracking_id):
    """
    Makale anahtar kelimelerini günceller. Sadece editörler tarafından kullanılabilir.
    """
    # Editör yetkilendirmesi
    is_editor = request.GET.get('is_editor', 'false').lower() == 'true'

    if not is_editor:
        return Response({'error': 'Yetkilendirme hatası'}, status=status.HTTP_403_FORBIDDEN)

    try:
        paper = Paper.objects.get(tracking_id=tracking_id)

        # Yeni anahtar kelimeleri al
        keywords = request.data.get('keywords', '')

        # Anahtar kelimeleri güncelle
        paper.keywords = keywords
        paper.save()

        # Log kaydı ekle
        PaperLog.objects.create(
            paper=paper,
            action="Anahtar kelimeler güncellendi",
            details=f"Yeni anahtar kelimeler: {keywords}"
        )

        return Response({
            'success': True,
            'keywords': keywords
        })

    except Paper.DoesNotExist:
        return Response({'error': 'Makale bulunamadı'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': f'Anahtar kelimeler güncellenirken hata oluştu: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def update_field(request, tracking_id):
    """
    Makale alanını (field) günceller. Sadece editörler tarafından kullanılabilir.
    """
    # Editör yetkilendirmesi
    is_editor = request.GET.get('is_editor', 'false').lower() == 'true'

    if not is_editor:
        return Response({'error': 'Yetkilendirme hatası'}, status=status.HTTP_403_FORBIDDEN)

    try:
        paper = Paper.objects.get(tracking_id=tracking_id)

        # Yeni alanı al
        field = request.data.get('field', '')
        
        # Field değeri FIELD_CHOICES içinde var mı kontrol et
        valid_fields = [choice[0] for choice in Paper.FIELD_CHOICES]
        if field and field not in valid_fields:
            return Response({'error': 'Geçersiz alan değeri'}, status=status.HTTP_400_BAD_REQUEST)

        # Alanı güncelle
        paper.field = field
        paper.save()

        # Log kaydı ekle
        field_display = dict(Paper.FIELD_CHOICES).get(field, 'Not Selected')
        PaperLog.objects.create(
            paper=paper,
            action="Alan güncellendi",
            details=f"Yeni alan: {field_display}"
        )

        return Response({
            'success': True,
            'field': field,
            'field_display': field_display
        })

    except Paper.DoesNotExist:
        return Response({'error': 'Makale bulunamadı'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': f'Alan güncellenirken hata oluştu: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
