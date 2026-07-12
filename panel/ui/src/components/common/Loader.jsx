import React from 'react';
import './Loader.css';

export default function Loader({ fullScreen = true, text = "Loading..." }) {
    const loaderContent = (
        <div className="pl">
            <div className="pl__dot"></div>
            <div className="pl__dot"></div>
            <div className="pl__dot"></div>
            <div className="pl__dot"></div>
            <div className="pl__dot"></div>
            <div className="pl__dot"></div>
            <div className="pl__dot"></div>
            <div className="pl__dot"></div>
            <div className="pl__dot"></div>
            <div className="pl__dot"></div>
            <div className="pl__dot"></div>
            <div className="pl__dot"></div>
            <div className="pl__text">{text}</div>
        </div>
    );

    if (fullScreen) {
        return (
            <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/90 backdrop-blur-sm">
                {loaderContent}
            </div>
        );
    }

    return (
        <div className="flex items-center justify-center p-8">
            {loaderContent}
        </div>
    );
}
