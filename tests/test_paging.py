import os
import sys

# Change directory to parent directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from luxy import Objects

def test_page_size():
    obj = Objects()
    assert obj.page_size == 20

def test_num_pages_calculation():
    obj = Objects()
    # Mock the num_results
    obj.num_results = 100
    assert obj.num_pages() == 5  # 100/20 = 5

    obj.num_results = 101
    assert obj.num_pages() == 6  # 101/20 = 5.05 -> 6 pages

    obj.num_results = 20
    assert obj.num_pages() == 1  # Exact division

    obj.num_results = 0
    assert obj.num_pages() == 0  # No results

def test_page_urls_generation():
    obj = Objects()
    obj.filter(name="test").get()
    base_url = obj.url
    
    # Test with 3 pages
    obj.num_results = 50  # This will create 3 pages
    urls = obj.get_page_urls()
    
    assert len(urls) == 3
    assert urls[0] == base_url + "&page=1"
    assert urls[1] == base_url + "&page=2"
    assert urls[2] == base_url + "&page=3"

def test_page_data_all_validation():
    obj = Objects()
    obj.filter(name="test").get()
    
    # Test invalid start page
    obj.num_results = 20  # 1 page total
    pages = list(obj.get_page_data_all(start_page=0, end_page=1))  # Start page > total pages
    assert len(pages) == 1  # Should return empty when start_page > total pages

    obj = Objects()
    obj.filter(name="test").get()
    # Test end page validation
    pages = list(obj.get_page_data_all(start_page=0, end_page=5))  # End page > total pages
    assert len(pages) == 5  # Should only return existing pages
