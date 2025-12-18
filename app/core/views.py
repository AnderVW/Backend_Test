from django.shortcuts import render
from django.contrib.auth.decorators import login_required

def index(request):
    return render(request, 'index.html')

@login_required
def my_assets(request):
    """View for managing user assets"""
    return render(request, 'virtufit/my_assets.html')

@login_required
def virtual_fit(request):
    """View for virtual fit feature"""
    return render(request, 'virtufit/virtual_fit.html')

@login_required
def profile_page(request):
    """View for testing user profile read/update"""
    return render(request, 'userprofile/profile_page.html')

