"""Countries API built with Django REST Framework (single-file Django project).

Run:  gunicorn --chdir drf_app project:application --workers 1 --bind 127.0.0.1:8001
Docs: http://127.0.0.1:8001/api/docs/   (Swagger UI via drf-spectacular)
"""
import sys
import time
from pathlib import Path

from django.conf import settings

settings.configure(
    DEBUG=False,
    SECRET_KEY="dev-only-not-secret",
    ROOT_URLCONF="project",
    ALLOWED_HOSTS=["*"],
    INSTALLED_APPS=[
        "django.contrib.contenttypes",
        "django.contrib.auth",
        "rest_framework",
        "drf_spectacular",
    ],
    MIDDLEWARE=[],
    TEMPLATES=[{"BACKEND": "django.template.backends.django.DjangoTemplates", "APP_DIRS": True}],
    REST_FRAMEWORK={
        "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
        "DEFAULT_AUTHENTICATION_CLASSES": [],
        "DEFAULT_PERMISSION_CLASSES": [],
        "UNAUTHENTICATED_USER": None,
        "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    },
    SPECTACULAR_SETTINGS={"TITLE": "Countries API (DRF)", "VERSION": "1.0.0"},
)

import django  # noqa: E402

django.setup()

from django.core.wsgi import get_wsgi_application  # noqa: E402
from django.urls import path  # noqa: E402
from drf_spectacular.utils import OpenApiParameter, extend_schema  # noqa: E402
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView  # noqa: E402
from rest_framework import serializers, status  # noqa: E402
from rest_framework.response import Response  # noqa: E402
from rest_framework.views import APIView  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "data"))
from loader import load_countries  # noqa: E402

REGIONS = ["Africa", "Americas", "Asia", "Europe", "Oceania", "Antarctic"]
COUNTRIES = {c["cca2"]: c for c in load_countries()}


class CountrySerializer(serializers.Serializer):
    name = serializers.CharField(min_length=1, max_length=100)
    cca2 = serializers.RegexField(r"^[A-Z]{2}$")
    cca3 = serializers.RegexField(r"^[A-Z]{3}$")
    region = serializers.ChoiceField(choices=REGIONS)
    capital = serializers.CharField(max_length=100, required=False, allow_blank=True)
    population = serializers.IntegerField(min_value=0)
    area = serializers.FloatField(min_value=0, required=False)


class ListQuerySerializer(serializers.Serializer):
    region = serializers.ChoiceField(choices=REGIONS, required=False)
    search = serializers.CharField(max_length=50, required=False)
    min_population = serializers.IntegerField(min_value=0, required=False)


class SlowQuerySerializer(serializers.Serializer):
    delay = serializers.FloatField(min_value=0, max_value=1, default=0.2)


class CountryList(APIView):
    @extend_schema(parameters=[ListQuerySerializer], responses=CountrySerializer(many=True))
    def get(self, request):
        q = ListQuerySerializer(data=request.query_params)
        q.is_valid(raise_exception=True)
        f = q.validated_data
        items = COUNTRIES.values()
        if "region" in f:
            items = [c for c in items if c["region"] == f["region"]]
        if "search" in f:
            items = [c for c in items if f["search"].lower() in c["name"].lower()]
        if "min_population" in f:
            items = [c for c in items if c["population"] >= f["min_population"]]
        return Response(CountrySerializer(list(items), many=True).data)

    @extend_schema(request=CountrySerializer, responses={201: CountrySerializer})
    def post(self, request):
        s = CountrySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        country = s.validated_data
        if country["cca2"] in COUNTRIES:
            return Response({"detail": "Country already exists"}, status=status.HTTP_409_CONFLICT)
        COUNTRIES[country["cca2"]] = dict(country)
        return Response(CountrySerializer(country).data, status=status.HTTP_201_CREATED)


class CountryDetail(APIView):
    @extend_schema(responses=CountrySerializer)
    def get(self, request, code):
        code = code.upper()
        if not code.isalpha() or len(code) not in (2, 3):
            return Response({"detail": "Code must be 2 or 3 letters"}, status=status.HTTP_400_BAD_REQUEST)
        for c in COUNTRIES.values():
            if code in (c["cca2"], c["cca3"]):
                return Response(CountrySerializer(c).data)
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)


class Slow(APIView):
    """Simulates a slow upstream call (blocking sleep, as a sync view would do)."""

    @extend_schema(parameters=[SlowQuerySerializer], responses={200: dict})
    def get(self, request):
        q = SlowQuerySerializer(data=request.query_params)
        q.is_valid(raise_exception=True)
        time.sleep(q.validated_data["delay"])
        return Response({"slept": q.validated_data["delay"]})


urlpatterns = [
    path("countries", CountryList.as_view()),
    path("countries/<str:code>", CountryDetail.as_view()),
    path("slow", Slow.as_view()),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema")),
]

application = get_wsgi_application()
