# -*- coding: utf-8 -*-
"""Standalone safe database initializer for the Yasna postal module."""
from forms.postal import initialize_postal_db
if __name__ == '__main__':
    initialize_postal_db()
    print('Yasna postal tables are ready.')
