import './Loading.css';

const Loading = ({ size = 'md', fullScreen = false }) => {
    if (fullScreen) {
        return (
            <div className="loading-fullscreen">
                <div className={`loading-spinner loading-${size}`}></div>
                <p className="loading-text">Loading...</p>
            </div>
        );
    }

    return <div className={`loading-spinner loading-${size}`}></div>;
};

export default Loading;
