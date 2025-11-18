from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from datetime import datetime, timedelta
import pandas as pd
from models.recommendation_engine import RecommendationEngine

# Initialize Flask app
app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = 'your-super-secret-jwt-key-change-in-production'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
app.config['JWT_ALGORITHM'] = 'HS256'

# Initialize extensions
CORS(app, origins=["http://localhost:3000", "http://127.0.0.1:3000"])
jwt = JWTManager(app)

# Initialize recommendation engine
recommender = RecommendationEngine()

# Mock user database (in production, use a real database)
users_db = {
    'alex@example.com': {
        'id': 'user1',
        'name': 'Alex Johnson',
        'email': 'alex@example.com',
        'password': 'password123'  # In production, use hashed passwords
    },
    'sarah@example.com': {
        'id': 'user2', 
        'name': 'Sarah Miller',
        'email': 'sarah@example.com',
        'password': 'password123'
    },
    'mike@example.com': {
        'id': 'user3',
        'name': 'Mike Chen', 
        'email': 'mike@example.com',
        'password': 'password123'
    }
}

# Authentication endpoints
@app.route('/api/auth/login', methods=['POST'])
def login():
    """User login endpoint"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({
                'success': False,
                'message': 'Email and password are required'
            }), 400
        
        # Check user credentials
        user = users_db.get(email)
        if user and user['password'] == password:  # In production, use proper password hashing
            access_token = create_access_token(identity=user['id'])
            return jsonify({
                'success': True,
                'message': 'Login successful',
                'user': {
                    'id': user['id'],
                    'name': user['name'],
                    'email': user['email']
                },
                'access_token': access_token
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Invalid email or password'
            }), 401
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Login failed: {str(e)}'
        }), 500

@app.route('/api/auth/register', methods=['POST'])
def register():
    """User registration endpoint"""
    try:
        data = request.get_json()
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        
        if not all([name, email, password]):
            return jsonify({
                'success': False,
                'message': 'Name, email, and password are required'
            }), 400
        
        # Check if user already exists
        if email in users_db:
            return jsonify({
                'success': False,
                'message': 'User already exists'
            }), 409
        
        # Create new user (in production, hash the password)
        user_id = f'user{len(users_db) + 1}'
        users_db[email] = {
            'id': user_id,
            'name': name,
            'email': email,
            'password': password
        }
        
        # Initialize user profile in recommendation engine
        recommender.user_profiles[user_id] = {
            'name': name,
            'email': email,
            'browsing_history': [],
            'purchase_history': [],
            'favorite_categories': [],
            'search_history': []
        }
        
        access_token = create_access_token(identity=user_id)
        return jsonify({
            'success': True,
            'message': 'Registration successful',
            'user': {
                'id': user_id,
                'name': name,
                'email': email
            },
            'access_token': access_token
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Registration failed: {str(e)}'
        }), 500

# Recommendation endpoints
@app.route('/api/recommendations', methods=['GET'])
@jwt_required()
def get_recommendations():
    """Get personalized recommendations for authenticated user"""
    try:
        user_id = get_jwt_identity()
        top_n = request.args.get('limit', 12, type=int)
        
        recommendations = recommender.generate_recommendations(user_id, top_n)
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'recommendations': recommendations,
            'count': len(recommendations),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to get recommendations: {str(e)}'
        }), 500

@app.route('/api/products', methods=['GET'])
def get_products():
    """Get all products with optional filtering"""
    try:
        category = request.args.get('category')
        max_price = request.args.get('max_price', type=float)
        min_rating = request.args.get('min_rating', 0, type=float)
        featured = request.args.get('featured', type=bool)
        
        products_df = recommender.products.copy()
        
        # Apply filters
        if category:
            products_df = products_df[products_df['category'] == category]
        if max_price:
            products_df = products_df[products_df['price'] <= max_price]
        if min_rating:
            products_df = products_df[products_df['rating'] >= min_rating]
        if featured is not None:
            products_df = products_df[products_df['featured'] == featured]
        
        products = products_df.to_dict('records')
        
        return jsonify({
            'success': True,
            'products': products,
            'count': len(products),
            'filters': {
                'category': category,
                'max_price': max_price,
                'min_rating': min_rating,
                'featured': featured
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to get products: {str(e)}'
        }), 500

@app.route('/api/products/search', methods=['GET'])
@jwt_required()
def search_products():
    """Search products with query and filters"""
    try:
        user_id = get_jwt_identity()
        query = request.args.get('q', '')
        category = request.args.get('category')
        max_price = request.args.get('max_price', type=float)
        min_rating = request.args.get('min_rating', 0, type=float)
        
        if not query:
            return jsonify({
                'success': False,
                'message': 'Search query is required'
            }), 400
        
        # Add to user's search history
        recommender.add_to_user_history(user_id, query)
        
        # Perform search
        results_df = recommender.search_products(
            query=query,
            category=category,
            max_price=max_price,
            min_rating=min_rating
        )
        
        results = results_df.to_dict('records')
        
        return jsonify({
            'success': True,
            'query': query,
            'results': results,
            'count': len(results),
            'filters': {
                'category': category,
                'max_price': max_price,
                'min_rating': min_rating
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Search failed: {str(e)}'
        }), 500

@app.route('/api/user/history', methods=['GET'])
@jwt_required()
def get_user_history():
    """Get user's search history"""
    try:
        user_id = get_jwt_identity()
        search_history = recommender.get_user_search_history(user_id)
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'search_history': search_history,
            'count': len(search_history)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to get history: {str(e)}'
        }), 500

@app.route('/api/user/history/clear', methods=['DELETE'])
@jwt_required()
def clear_user_history():
    """Clear user's search history"""
    try:
        user_id = get_jwt_identity()
        success = recommender.clear_user_history(user_id)
        
        return jsonify({
            'success': success,
            'message': 'Search history cleared successfully' if success else 'Failed to clear history'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to clear history: {str(e)}'
        }), 500

@app.route('/api/categories', methods=['GET'])
def get_categories():
    """Get all available product categories"""
    try:
        categories = recommender.products['category'].unique().tolist()
        
        return jsonify({
            'success': True,
            'categories': categories,
            'count': len(categories)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to get categories: {str(e)}'
        }), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get application statistics"""
    try:
        total_products = len(recommender.products)
        total_users = len(recommender.user_profiles)
        categories = recommender.products['category'].value_counts().to_dict()
        avg_rating = recommender.products['rating'].mean()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_products': total_products,
                'total_users': total_users,
                'categories': categories,
                'average_rating': round(avg_rating, 2),
                'featured_products': len(recommender.products[recommender.products['featured'] == True])
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to get stats: {str(e)}'
        }), 500

# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'success': True,
        'message': 'SmartShop API is running',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'message': 'Endpoint not found'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'message': 'Internal server error'
    }), 500

if __name__ == '__main__':
    print("🚀 Starting SmartShop Recommendation Engine...")
    print(f"📦 Total Products: {len(recommender.products)}")
    print(f"👥 Total Users: {len(recommender.user_profiles)}")
    print(f"🔍 Available Categories: {list(recommender.products['category'].unique())}")
    print("🌟 Server running on http://localhost:5000")
    
    app.run(debug=True, host='0.0.0.0', port=5000)