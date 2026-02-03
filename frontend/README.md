# Microfinance AI Frontend

Modern React frontend for the Microfinance AI Analysis API.

## Features

- **Ask AI Interface**: Chat-style conversational AI for analyzing microfinance data
- **CSV Upload**: Drag-and-drop file upload with validation
- **Dashboard**: Statistics overview with top performers and risk analysis
- **Modern UI**: Glassmorphism design with smooth animations
- **Responsive**: Mobile-friendly responsive design

## Tech Stack

- React 18
- Vite
- React Router v6
- Axios
- Lucide React (icons)
- Modern CSS

## Getting Started

### Prerequisites

- Node.js 18+ installed
- Backend API running on `http://localhost:5000`

### Installation

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The app will be available at `http://localhost:5173`

### Build for Production

```bash
npm run build
```

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── Layout/         # Header and layout components
│   │   ├── Ask/           # Chat interface
│   │   ├── Upload/        # File upload component
│   │   ├── Dashboard/     # Dashboard with stats
│   │   └── Common/        # Reusable components
│   ├── services/
│   │   └── api.js        # API service layer
│   ├── styles/
│   │   └── globals.css   # Global styles and design system
│   ├── App.jsx           # Main app with routing
│   └── main.jsx          # Entry point
├── index.html
├── package.json
└── vite.config.js
```

## API Configuration

The API base URL is configured in `src/services/api.js`. Update this if your backend is running on a different port:

```javascript
const API_BASE_URL = 'http://localhost:5000/api';
```

## Available Pages

- **/** - Ask AI (Chat Interface)
- **/upload** - Upload CSV files
- **/dashboard** - View statistics and analytics
- **/clients** - Coming soon
- **/risk** - Coming soon

## Design System

The app uses a dark theme with glassmorphism effects:

- **Colors**: Purple/violet gradients for primary actions
- **Typography**: Inter font family
- **Effects**: Backdrop blur, smooth transitions, hover animations
- **Responsive**: Mobile-first approach

## Usage

### 1. Upload Data

1. Navigate to Upload page
2. Drag and drop a CSV file or click to browse
3. Upload the file
4. View the success message with statistics

### 2. Ask Questions

1. Go to the home page (Ask AI)
2. Type your question or use quick action buttons
3. Get instant AI-powered responses

Examples:
- "Show me statistics"
- "Analyze client John Doe"
- "Show top clients"
- "Risk analysis"

### 3. View Dashboard

1. Navigate to Dashboard
2. View portfolio statistics
3. See top performing clients
4. Check risk analysis

## Development

### Running Development Server

```bash
npm run dev
```

### Building for Production

```bash
npm run build
npm run preview  # Preview production build
```

## Environment Variables

No environment variables are required by default. The API URL is hardcoded in the service layer.

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)

## License

MIT
