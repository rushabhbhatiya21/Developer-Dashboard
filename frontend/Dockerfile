FROM node:iron-bookworm as base

WORKDIR /frontend

# Copy package files first
COPY package*.json ./

# COPY .env.local .

# Install dependencies
RUN npm install

# Copy source code
COPY . .

# Development stage
FROM base as development
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# Production stage
FROM base as production
RUN npm run build

# Expose the port
EXPOSE 5173

# Start the application when container runs (not during build)
CMD ["npm", "run", "dev"]