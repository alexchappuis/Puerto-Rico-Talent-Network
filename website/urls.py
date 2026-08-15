from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about_us, name='about_us'),
    path('join/', views.join_the_network, name='join_the_network'),
    path('events/', views.events, name='events'),
    path('events/<slug:slug>/register/', views.event_register, name='event_register'),
]