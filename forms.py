from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    FloatField,
    IntegerField,
    SelectField,
    TextAreaField,
    PasswordField,
    BooleanField,
)
from wtforms.validators import (
    DataRequired,
    InputRequired,
    Email,
    Length,
    NumberRange,
    Optional,
    EqualTo,
)


class PredictForm(FlaskForm):
    location = StringField("Location", validators=[Optional(), Length(max=120)])
    weather_source = StringField("Weather Source", default="manual", validators=[Optional()])

    temperature = FloatField(
        "Temperature (°C)",
        validators=[
            InputRequired(message="Temperature is required"),
            NumberRange(min=0, max=50, message="Temperature must be between 0 and 50 °C"),
        ],
    )
    humidity = FloatField(
        "Humidity (%)",
        validators=[
            InputRequired(message="Humidity is required"),
            NumberRange(min=0, max=100, message="Humidity must be between 0 and 100 %"),
        ],
    )
    moisture = FloatField(
        "Soil Moisture (%)",
        validators=[
            InputRequired(message="Soil moisture is required"),
            NumberRange(min=0, max=100, message="Soil moisture must be between 0 and 100 %"),
        ],
    )

    soil = SelectField("Soil Type", validators=[DataRequired(message="Soil type is required")])
    crop = SelectField("Crop Type", validators=[DataRequired(message="Crop type is required")])

    nitrogen = IntegerField(
        "Nitrogen (N)",
        validators=[
            InputRequired(message="Nitrogen is required"),
            NumberRange(min=0, max=255, message="Nitrogen must be between 0 and 255"),
        ],
    )
    phosphorous = IntegerField(
        "Phosphorous (P)",
        validators=[
            InputRequired(message="Phosphorous is required"),
            NumberRange(min=0, max=255, message="Phosphorous must be between 0 and 255"),
        ],
    )
    potassium = IntegerField(
        "Potassium (K)",
        validators=[
            InputRequired(message="Potassium is required"),
            NumberRange(min=0, max=255, message="Potassium must be between 0 and 255"),
        ],
    )

    rating_n = SelectField("Nitrogen rating", choices=[("Low", "Low"), ("Medium", "Medium"), ("High", "High")], default="Medium")
    rating_p = SelectField("Phosphorous rating", choices=[("Low", "Low"), ("Medium", "Medium"), ("High", "High")], default="Medium")
    rating_k = SelectField("Potassium rating", choices=[("Low", "Low"), ("Medium", "Medium"), ("High", "High")], default="Medium")

    area_value = FloatField(
        "Area",
        default=1.0,
        validators=[
            Optional(),
            NumberRange(min=0.1, max=1000.0, message="Area must be between 0.1 and 1000"),
        ],
    )
    area_unit = SelectField("Unit", choices=[("acre", "Acres"), ("ha", "Hectares")], default="acre")


class ContactForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=100)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    message = TextAreaField("Message", validators=[DataRequired(), Length(max=2000)])


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Remember Me")


class RegisterForm(FlaskForm):
    name = StringField("Full Name", validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8, message="Password must be at least 8 characters")])
    confirm_password = PasswordField("Confirm Password", validators=[DataRequired(), EqualTo("password", message="Passwords must match")])
    preferred_language = SelectField("Preferred Language", choices=[("en", "English"), ("te", "Telugu"), ("ta", "Tamil"), ("hi", "Hindi")], default="en")

