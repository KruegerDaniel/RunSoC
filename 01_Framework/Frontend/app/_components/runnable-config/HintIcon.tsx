'use client';

import {Tooltip} from '@radix-ui/themes';
import {QuestionMarkCircledIcon} from '@radix-ui/react-icons';

interface HintIconProps {
    hint: string;
    side?: 'top' | 'right' | 'bottom' | 'left';
}

const HintIcon = ({hint, side = 'top'}: HintIconProps) => {
    return (
        <Tooltip content={hint} side={side}>
            <QuestionMarkCircledIcon
                className="inline-block ml-1 cursor-pointer text-gray-500 hover:text-gray-700"
                aria-label="Help"
            />
        </Tooltip>
    );
};

export default HintIcon;
