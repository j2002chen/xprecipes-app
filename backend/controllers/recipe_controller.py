import bleach
import uuid
from flask import request
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from cerberus import Validator
from PIL import Image
from backend.models import Recipe 
from backend.S3_helpers import get_image_url,upload_to_s3,delete_from_s3
from backend import app, db

validation_schema = {
    "title": {
        "type": "string",
        "required": True,
        "minlength": 3,
        "maxlength": 100
    },
    "ingredients": {
        "type": "string",
        "required": True,
        "minlength": 1,
        "maxlength": 100
    },
    "ingredient_quantity": {
        "type": "float",
        "required": True
    },
    "unit": {
        "type": "string",
        "required": True,
        "allowed": ["oz", "g", "cup", "tsp", "tbsp", "ml", "l"]
    },
    "calories": {
        "type": "integer",
        "required": True
    },
    "cooktime": {
        "type": "integer",
        "required": True
    },
    "image": {
    "type": "file",
    "required": False,
    "allowed": ["jpg", "jpeg", "png"]
    }
}

class RecipeCreate(Resource):
    @jwt_required
    def post(self):   
        data = request.json
        v = Validator(validation_schema)
        if not v.validate(data):
            return v.errors, 400
        title = bleach.clean(request.json["title"])
        ingredients = bleach.clean(request.json["ingredients"])
        ingredient_quantity = request.json["ingredient_quantity"]
        unit = bleach.clean(request.json["unit"])
        if "image" in request.files:
            image = request.files["image"]
            if not image.filename.endswith((".jpg", ".jpeg", ".png")):
                return {"message": "Invalid file type"}, 400
            if image.content_length > 5 * 1024 * 1024: # 5MB
                return {"message": "File size exceeds 5MB"}, 400
            try:
                img = Image.open(image)
                img.verify()
            except Exception as e:
                return {"message": "Image is corrupt"}, 400
            filename = str(uuid.uuid4()) + image.filename.split(".")[-1]
            upload_to_s3(app, image, "xprecipes-images", filename)
            image_key = filename
        else:
            image_key = "default_image_key"
        calories = request.json["calories"]
        cooktime = request.json["cooktime"]
        recipe = Recipe(title=title, ingredients=ingredients, ingredient_quantity=ingredient_quantity
                        ,unit=unit,image_key=image_key,calories=calories,cooktime=cooktime)
        db.session.add(recipe)
        db.session.commit()
        return recipe.to_dict(), 201

class RecipeUpdate(Resource):
    @jwt_required
    def put(self, recipe_id):    
        data = request.json
        v = Validator(validation_schema)
        if not v.validate(data):
            return v.errors, 400
        title = bleach.clean(request.json["title"])
        ingredients = bleach.clean(request.json["ingredients"])
        ingredient_quantity = request.json["ingredient_quantity"]
        unit = bleach.clean(request.json["unit"])
        calories = request.json["calories"]
        cooktime = request.json["cooktime"]
        recipe = Recipe.query.filter_by(id=recipe_id).first()
        recipe.title = title
        recipe.ingredients = ingredients
        recipe.quantity = ingredient_quantity
        recipe.unit = unit
        recipe.calories = calories
        recipe.cooktime = cooktime 
        if "image" in request.files:
            image = request.files["image"]
            if not image.filename.endswith((".jpg", ".jpeg", ".png")):
                return {"message": "Invalid file type"}, 400
            if image.content_length > 5 * 1024 * 1024: # 5MB
                return {"message": "File size exceeds 5MB"}, 400
            try:
                img = Image.open(image)
                img.verify()
            except Exception as e:
                return {"message": "Image is corrupt"}, 400
            filename = str(uuid.uuid4()) + image.filename.split(".")[-1]
            upload_to_s3(app, image, "xprecipes-images", filename)
            image_key = filename
            recipe.image_key = image_key
        db.session.commit()
        return recipe.to_dict(), 200


class RecipeDelete(Resource):
    @jwt_required
    def delete(self,recipe_id):
        recipe = Recipe.query.filter_by(id=recipe_id).first()
        if recipe is None:
            return {"message": "Recipe not found"}, 404
        image_key = recipe.image_key
        if image_key != "default_image_key":
            delete_from_s3(app, image_key, "xprecipes-images")
        recipe.delete()
        return {"message": "Recipe deleted"}, 200


class RecipeList(Resource):
    @jwt_required
    def get(self, recipe_id):
        current_user = get_jwt_identity()
        recipe = Recipe.query.filter_by(id=recipe_id, user_id=current_user).first()
        if recipe is None:
            return {"message": "Recipe not found"}, 404
        recipe_data = recipe.to_dict()
        recipe_data["image_url"] = get_image_url(recipe, recipe.image_key, "xprecipes_images")
        return recipe_data


