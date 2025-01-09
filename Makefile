all:
	@echo "make migrations           - Make migrations"
	@echo "make migrate              - Migrate"
	@echo "make run                  - Run development server"
	@exit 0


migrations:
	python manage.py makemigrations

migrate:
	python manage.py migrate

run:
	python manage.py runserver
