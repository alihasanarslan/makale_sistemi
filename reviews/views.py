from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from papers.models import Paper, PaperLog
from .models import Review
from users.models import User
from papers.pdf_service import PDFAnonymizer

@api_view(['GET'])
def review_list(request):

    reviewer_email = request.GET.get('email', '')
    if not reviewer_email:
        return Response({'error': 'E-posta gerekli'}, status=status.HTTP_400_BAD_REQUEST)

    try:

        reviews = Review.objects.filter(reviewer__email=reviewer_email)
        review_list = []

        for review in reviews:
            paper = review.paper

            assigned_at = review.assigned_at.isoformat() if review.assigned_at else None
            updated_at = review.updated_at.isoformat() if review.updated_at else None
            
            review_info = {
                'tracking_id': paper.tracking_id,
                'title': paper.title or f"Paper {paper.tracking_id}",
                'status': review.status,
                'assigned_at': assigned_at,
                'updated_at': updated_at,
                'recommendation': review.recommendation,
                'is_anonymized': hasattr(paper, 'anonymized')
            }
            review_list.append(review_info)

        return Response(review_list)
    except Exception as e:
        print(f"Review listesi hatası: {e}")
        return Response({'error': 'Review listesi alınırken bir hata oluştu'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET', 'POST'])
def submit_review(request, tracking_id):
    reviewer_email = request.GET.get('email', '')
    if not reviewer_email:
        return Response({'error': 'E-posta gerekli'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        paper = Paper.objects.get(tracking_id=tracking_id)
        review = Review.objects.get(paper=paper, reviewer__email=reviewer_email)
    except (Paper.DoesNotExist, Review.DoesNotExist):
        return Response({'error': 'Değerlendirme bulunamadı'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        if not hasattr(paper, 'anonymized'):
            return Response({'error': 'Bu makale henüz anonimleştirilmemiş'}, status=status.HTTP_400_BAD_REQUEST)

        print(f"Anonimleştirilmiş PDF URL: {paper.anonymized.file.url}")
        print(f"Anonimleştirilmiş PDF path: {paper.anonymized.file.path}")
        import os
        print(f"Dosya mevcut mu: {os.path.exists(paper.anonymized.file.path)}")


        anonymized_file_url = f"/media/papers/anonymized/{paper.tracking_id}_anonymized.pdf"

        return Response({
            'tracking_id': paper.tracking_id,
            'title': paper.title or f"Paper {paper.tracking_id}",
            'anonymized_file_url': anonymized_file_url,
            'status': review.status,
            'comments': review.comments,
            'recommendation': review.recommendation
        })

    elif request.method == 'POST':

        comments = request.data.get('comments', '')
        recommendation = request.data.get('recommendation', '')
        
        if not comments or not recommendation:
            return Response({'error': 'Yorum ve tavsiye gerekli'}, status=status.HTTP_400_BAD_REQUEST)

        if recommendation not in ['accept', 'minor_revision', 'major_revision', 'reject']:
            return Response({'error': 'Geçersiz tavsiye'}, status=status.HTTP_400_BAD_REQUEST)


        try:

            if not hasattr(paper, 'anonymized'):
                return Response({'error': 'Bu makale henüz anonimleştirilmemiş'}, status=status.HTTP_400_BAD_REQUEST)
            
            import fitz
            from datetime import datetime
            import os
            from django.conf import settings
            

            pdf_path = paper.anonymized.file.path
            if not os.path.exists(pdf_path):
                pdf_path = os.path.join(settings.MEDIA_ROOT, f"papers/anonymized/{paper.tracking_id}_anonymized.pdf")
                if not os.path.exists(pdf_path):

                    anonymized_folder = os.path.join(settings.MEDIA_ROOT, "papers/anonymized")
                    possible_files = [os.path.join(anonymized_folder, f) for f in os.listdir(anonymized_folder)]
                    matching_files = [f for f in possible_files if paper.tracking_id in f]
                    
                    if matching_files:
                        pdf_path = matching_files[0]
                    else:
                        return Response({'error': f'PDF dosyası bulunamadı: {pdf_path}'}, 
                                     status=status.HTTP_404_NOT_FOUND)
            
            print(f"Kullanılacak PDF yolu: {pdf_path}")
            

            review_file_name = f"{paper.tracking_id}_reviewed.pdf"
            review_file_path = os.path.join(settings.MEDIA_ROOT, f"reviews/{review_file_name}")
            

            os.makedirs(os.path.dirname(review_file_path), exist_ok=True)
            

            doc = fitz.open(pdf_path)
            

            page = doc.new_page(width=595, height=842)  # A4 boyutunda
            

            recommendation_map = {
                'accept': 'Kabul',
                'minor_revision': 'Küçük Revizyon',
                'major_revision': 'Büyük Revizyon',
                'reject': 'Red'
            }
            
            review_text = f"""
            MAKALE DEĞERLENDİRME RAPORU
            
            Makale ID: {paper.tracking_id}
            Değerlendirme Tarihi: {datetime.now().strftime('%d/%m/%Y %H:%M')}
            Hakem: {reviewer_email}
            
            TAVSİYE: {recommendation_map.get(recommendation, recommendation)}
            
            YORUMLAR:
            {comments}
            """
            

            page.insert_text((50, 50), review_text, fontsize=11)
            

            doc.save(review_file_path)
            doc.close()
            

            review_file_url = f"/media/reviews/{review_file_name}"
            review.comments = comments
            review.recommendation = recommendation
            review.status = 'completed'
            review.review_file = f"reviews/{review_file_name}"
            review.save()
            

            PaperLog.objects.create(
                paper=paper,
                action="Değerlendirme tamamlandı",
                details=f"Hakem: {reviewer_email}, Tavsiye: {recommendation_map.get(recommendation, recommendation)}"
            )
            

            paper.status = 'reviewed'
            paper.save()
            
            return Response({
                'message': 'Değerlendirme başarıyla kaydedildi',
                'review_file_url': review_file_url
            })
            
        except Exception as e:
            print(f"Değerlendirme eklerken hata: {e}")
            import traceback
            traceback.print_exc()
            return Response({'error': f'Değerlendirme eklenirken hata oluştu: {str(e)}'}, 
                           status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def review_status(request, tracking_id):
    reviewer_email = request.GET.get('email', '')
    if not reviewer_email:
        return Response({'error': 'E-posta gerekli'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        paper = Paper.objects.get(tracking_id=tracking_id)
        review = Review.objects.get(paper=paper, reviewer__email=reviewer_email)


        updated_at = review.updated_at.isoformat() if review.updated_at else None

        return Response({
            'status': review.status,
            'comments': review.comments,
            'recommendation': review.recommendation,
            'review_file_url': review.review_file.url if review.review_file else None,
            'updated_at': updated_at,
            'title': paper.title
        })

    except (Paper.DoesNotExist, Review.DoesNotExist):
        return Response({'error': 'Değerlendirme bulunamadı'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
def send_review_to_author(request, tracking_id):

    is_editor = request.GET.get('is_editor', 'false').lower() == 'true'

    if not is_editor:
        return Response({'error': 'Yetkilendirme hatası'}, status=status.HTTP_403_FORBIDDEN)

    try:
        paper = Paper.objects.get(tracking_id=tracking_id)
        

        if not paper.reviews.filter(status='completed').exists():
            return Response({'error': 'Bu makale için tamamlanmış bir değerlendirme bulunamadı'}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        review = paper.reviews.filter(status='completed').first()
        
        if not review.review_file:
            return Response({'error': 'Değerlendirme dosyası bulunamadı'}, 
                           status=status.HTTP_400_BAD_REQUEST)


        from django.conf import settings
        import os
        import fitz
        from datetime import datetime
        

        original_pdf_path = paper.original_file.path
        if not os.path.exists(original_pdf_path):
            return Response({'error': 'Orijinal PDF dosyası bulunamadı'}, 
                           status=status.HTTP_404_NOT_FOUND)
        

        review_pdf_path = review.review_file.path
        if not os.path.exists(review_pdf_path):
            return Response({'error': 'Değerlendirme dosyası bulunamadı'}, 
                           status=status.HTTP_404_NOT_FOUND)
        

        combined_file_name = f"{paper.tracking_id}_combined_review.pdf"
        combined_file_path = os.path.join(settings.MEDIA_ROOT, f"reviews/{combined_file_name}")
        

        os.makedirs(os.path.dirname(combined_file_path), exist_ok=True)
        
        try:

            original_doc = fitz.open(original_pdf_path)
            

            review_doc = fitz.open(review_pdf_path)
            

            review_page_count = len(review_doc)
            

            if review_page_count > 0:

                review_last_page = review_doc[review_page_count - 1]
                

                combined_doc = fitz.open()
                

                combined_doc.insert_pdf(original_doc)
                

                combined_doc.insert_pdf(review_doc, from_page=review_page_count-1, to_page=review_page_count-1)
                

                combined_doc.save(combined_file_path)
                

                combined_doc.close()
                
            else:

                combined_doc = fitz.open()
                combined_doc.insert_pdf(original_doc)
                combined_doc.save(combined_file_path)
                combined_doc.close()
                

            original_doc.close()
            review_doc.close()
            

            review_file_url = f"/media/reviews/{combined_file_name}"
            review.combined_review_file = f"reviews/{combined_file_name}"
            review.save()
            
        except Exception as e:
            return Response({'error': f'PDF işleme hatası: {str(e)}'}, 
                           status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

        PaperLog.objects.create(
            paper=paper,
            action="Değerlendirme yazara gönderildi",
            details=f"Değerlendirme şifresi çözülerek yazara gönderildi"
        )
        

        from reviews.models import Message
        Message.objects.create(
            paper=paper,
            sender_email="editor@makalesistemi.com",
            is_editor=True,
            content="Makaleniz değerlendirildi. Değerlendirme raporunu 'Değerlendirme Raporu' bölümünden indirebilirsiniz."
        )
        

        if review.recommendation == 'accept':
            paper.status = 'accepted'
        elif review.recommendation == 'reject':
            paper.status = 'rejected'
        elif review.recommendation in ['minor_revision', 'major_revision']:
            paper.status = 'revision'
        paper.save()
        

        from django.core.mail import send_mail
        
        recommendation_map = {
            'accept': 'Kabul',
            'minor_revision': 'Küçük Revizyon',
            'major_revision': 'Büyük Revizyon',
            'reject': 'Red'
        }
        
        send_mail(
            'Makaleniz Değerlendirildi',
            f'Merhaba,\n\n'
            f'"{paper.title or paper.tracking_id}" başlıklı makalenizin değerlendirmesi tamamlandı.\n\n'
            f'Değerlendirme Sonucu: {recommendation_map.get(review.recommendation, review.recommendation)}\n\n'
            f'Detaylı değerlendirme raporunu görmek için lütfen makale takip sistemine giriş yapın:\n'
            f'http://yourdomain.com/paper-status/\n\n'
            f'Makale ID: {paper.tracking_id}\n\n'
            f'Saygılarımızla,\n'
            f'Akademik Makale Sistemi',
            'noreply@makalesistemi.com',
            [paper.email],
            fail_silently=False,
        )
        
        return Response({
            'message': 'Değerlendirme yazara başarıyla gönderildi',
            'status': paper.status,
            'combined_review_file': review_file_url
        })
        
    except Paper.DoesNotExist:
        return Response({'error': 'Makale bulunamadı'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(f"Değerlendirme gönderme hatası: {e}")
        import traceback
        traceback.print_exc()
        return Response({'error': f'Değerlendirme gönderilirken hata oluştu: {str(e)}'}, 
                       status=status.HTTP_500_INTERNAL_SERVER_ERROR) 