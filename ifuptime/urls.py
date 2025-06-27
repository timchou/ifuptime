"""
URL configuration for ifuptime project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from monitoring import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'), # Placeholder for dashboard
    path('monitor/create/', views.monitor_create_view, name='monitor_create'),
    path('monitor/<int:monitor_id>/run_check/', views.run_check_view, name='run_check'),
    path('monitor/<int:monitor_id>/', views.monitor_detail_view, name='monitor_detail'),
    path('monitor/<int:monitor_id>/edit/', views.monitor_edit_view, name='monitor_edit'),
    path('monitor/<int:monitor_id>/delete/', views.monitor_delete_view, name='monitor_delete'),
    path('', views.login_view, name='home'), # Default to login page
]
