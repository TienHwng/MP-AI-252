db = db.getSiblingDB("HERA");
print("Initialized database: " + db.getName());

db.createCollection("users", {
	validator: {
		$jsonSchema: {
			bsonType: "object",
			required: ["user_id", "full_name", "email", "password_hash"],
			properties: {
				user_id: { bsonType: "string", description: "Primary Key" },
				full_name: { bsonType: "string" },
				email: { bsonType: "string" },
				password_hash: { bsonType: "string" },
			},
		},
	},
});

db.createCollection("ai_models", {
	validator: {
		$jsonSchema: {
			bsonType: "object",
			required: ["model_name", "model_version"],
			properties: {
				model_name: { bsonType: "string", description: "Primary Key" },
				model_version: { bsonType: "string" },
				description: { bsonType: "string" },
			},
		},
	},
});

db.createCollection("environments", {
	validator: {
		$jsonSchema: {
			bsonType: "object",
			required: ["env_id", "name"],
			properties: {
				env_id: { bsonType: "string", description: "Primary Key" },
				name: { bsonType: "string" },
				description: { bsonType: "string" },
			},
		},
	},
});

db.createCollection("devices", {
	validator: {
		$jsonSchema: {
			bsonType: "object",
			required: [
				"device_id",
				"env_id",
				"name",
				"category",
				"status",
				"anomaly_score",
			],
			properties: {
				device_id: { bsonType: "string", description: "Primary Key" },
				env_id: {
					bsonType: "string",
					description: "Foreign Key -> environments",
				},
				name: { bsonType: "string" },
				category: { bsonType: "string" },
				status: { bsonType: "string" },
				anomaly_score: { bsonType: ["double", "int"] },
                current_user_id: { bsonType: ["string", "null"], description: "User đang log in và sở hữu data hiện tại" }
			},
		},
	},
});

db.createCollection("interaction_sessions", {
	validator: {
		$jsonSchema: {
			bsonType: "object",
			required: [
				"chat_id",
				"user_id",
				"model_name",
				"env_id",
				"start_date",
				"latest_update",
				"input_text",
			],
			properties: {
				chat_id: { bsonType: "string", description: "Primary Key" },
				user_id: { bsonType: "string", description: "Foreign Key -> users" },
				model_name: {
					bsonType: "string",
					description: "Foreign Key -> ai_models",
				},
				env_id: {
					bsonType: "string",
					description: "Foreign Key -> environments",
				},
				start_date: { bsonType: "date" },
				latest_update: { bsonType: "date" },
				input_text: { bsonType: "string" },
			},
		},
	},
});

db.createCollection("activity_logs", {
	validator: {
		$jsonSchema: {
			bsonType: "object",
			required: [
				"log_id",
				"user_id",
				"env_id",
				"device_id",
				"event_type",
				"trigger_source",
				"response_text",
			],
			properties: {
				log_id: { bsonType: "string", description: "Primary Key" },
				user_id: { bsonType: "string", description: "Foreign Key -> users" },
				env_id: {
					bsonType: "string",
					description: "Foreign Key -> environments",
				},
				device_id: {
					bsonType: "string",
					description: "Foreign Key -> devices",
				},
				event_type: { bsonType: "string" },
				trigger_source: { bsonType: "string" },
				response_text: { bsonType: "string" },
			},
		},
	},
});

db.createCollection("telemetry_points", {
	timeseries: {
		timeField: "recorded_at", 
		metaField: "metadata", 
		granularity: "seconds",
	},
});

// Tạo Index cho các Foreign Keys để tăng tốc độ truy vấn
db.devices.createIndex({ env_id: 1 });
db.interaction_sessions.createIndex({ user_id: 1 });
db.interaction_sessions.createIndex({ env_id: 1 });
db.activity_logs.createIndex({ user_id: 1 });
db.activity_logs.createIndex({ device_id: 1 });

// Cập nhật index cho telemetry_points để query theo thiết bị và người dùng
db.telemetry_points.createIndex({ "metadata.device_id": 1 });
db.telemetry_points.createIndex({ "metadata.user_id": 1 });
db.telemetry_points.createIndex({ "metadata.device_id": 1, "metadata.user_id": 1 });

print("Database initialized with collections and indexes.");

print("Starting default data creation process...");

// Khởi tạo Environment và Device mặc định
db.environments.insertMany([
    { env_id: "env_0001", name: "Main Room", description: "Default testing environment" }
]);

db.devices.insertMany([
    { 
        device_id: "device_0001", 
        env_id: "env_0001", 
        name: "Yolo Uno", 
        category: "IoT Board", 
        status: "active", 
        anomaly_score: 0.0,
        current_user_id: null 
    }
]);

db.users.insertMany([
	{ user_id: "user_0001", full_name: "Nguyen Khanh Hung", email: "hung.nguyen1@hera.com", password_hash: "123456789" },
	{ user_id: "user_0002", full_name: "Nguyen Tien Hung", email: "hung.nguyen2@hera.com", password_hash: "123456789" },
	{ user_id: "user_0003", full_name: "Ho Lam Khanh Vy", email: "vy.ho123@hera.com", password_hash: "123456789" },
	{ user_id: "user_0004", full_name: "Tran Anh Duc", email: "duc.tran789@hera.com", password_hash: "123456789" },
	{ user_id: "user_0005", full_name: "Neji", email: "neji.kareshi@hera.com", password_hash: "123456789" },
]);

print("Users and defaults created successfully.");