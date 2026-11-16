from rest_framework import pagination


class PageNumberPagination(pagination.PageNumberPagination):
    page_size_query_param = "page_size"
    max_page_size = 100


class CursorPagination(pagination.CursorPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = "-created_at"
