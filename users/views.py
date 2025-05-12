from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import User
from reviews.models import Review


@api_view(['GET'])
def reviewer_list(request):

    is_editor = request.GET.get('is_editor', 'false').lower() == 'true'

    if not is_editor:
        return Response({'error': 'Yetkilendirme hatası'}, status=status.HTTP_403_FORBIDDEN)


    reviewers = User.objects.filter(is_reviewer=True)

    reviewer_list = []
    for reviewer in reviewers:

        total_reviews = Review.objects.filter(reviewer=reviewer).count()
        active_reviews = Review.objects.filter(reviewer=reviewer, status__in=['assigned', 'in_progress']).count()

        reviewer_info = {
            'id': reviewer.id,
            'email': reviewer.email,
            'total_reviews': total_reviews,
            'active_reviews': active_reviews
        }
        reviewer_list.append(reviewer_info)

    return Response(reviewer_list)


@api_view(['POST'])
def add_reviewer(request):

    is_editor = request.GET.get('is_editor', 'false').lower() == 'true'

    if not is_editor:
        return Response({'error': 'Yetkilendirme hatası'}, status=status.HTTP_403_FORBIDDEN)


    email = request.data.get('email', '')
    name = request.data.get('name', '')
    specialty = request.data.get('specialty', '')

    if not email:
        return Response({'error': 'E-posta adresi gerekli'}, status=status.HTTP_400_BAD_REQUEST)


    if User.objects.filter(email=email).exists():
        existing_user = User.objects.get(email=email)

        if not existing_user.is_reviewer:
            existing_user.is_reviewer = True
            existing_user.save()
            return Response({'message': 'Kullanıcı hakem olarak güncellendi', 'id': existing_user.id})
        else:
            return Response({'error': 'Bu e-posta adresi zaten bir hakeme ait'}, status=status.HTTP_400_BAD_REQUEST)


    reviewer = User.objects.create(
        email=email,
        is_reviewer=True
    )

    return Response({'message': 'Hakem başarıyla eklendi', 'id': reviewer.id})

@api_view(['DELETE'])
def delete_reviewer(request, reviewer_id):

    is_editor = request.GET.get('is_editor', 'false').lower() == 'true'

    if not is_editor:
        return Response({'error': 'Yetkilendirme hatası'}, status=status.HTTP_403_FORBIDDEN)

    reviewer = get_object_or_404(User, id=reviewer_id, is_reviewer=True)


    if Review.objects.filter(reviewer=reviewer, status__in=['assigned', 'in_progress']).exists():
        return Response({'error': 'Bu hakemin aktif değerlendirmeleri var, silemezsiniz'},
                        status=status.HTTP_400_BAD_REQUEST)

    reviewer.delete()

    return Response({'message': 'Hakem başarıyla silindi'})