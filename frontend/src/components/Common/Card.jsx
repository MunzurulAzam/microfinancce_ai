import './Card.css';

const Card = ({
    children,
    className = '',
    hoverable = false,
    onClick
}) => {
    const hoverClass = hoverable ? 'card-hoverable' : '';

    return (
        <div
            className={`card ${hoverClass} ${className}`.trim()}
            onClick={onClick}
        >
            {children}
        </div>
    );
};

export default Card;
