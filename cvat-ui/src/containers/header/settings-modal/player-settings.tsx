// Copyright (C) 2020-2022 Intel Corporation
//
// SPDX-License-Identifier: MIT

import { connect } from 'react-redux';

import PlayerSettingsComponent from 'components/header/settings-modal/player-settings';
import {
    changeFrameStep,
    changeFrameSpeed,
    switchResetZoom,
    switchRotateAll,
    changeCanvasBackgroundColor,
    switchSmoothImage,
    switchShowingDeletedFrames,
} from 'actions/settings-actions';
import { DimensionType, getCore } from 'cvat-core-wrapper';
import { CombinedState, FrameSpeed } from 'reducers';

interface StateToProps {
    frameStep: number;
    frameSpeed: FrameSpeed;
    resetZoom: boolean;
    rotateAll: boolean;
    smoothImage: boolean;
    canvasBackgroundColor: string;
    showDeletedFrames: boolean;
    imageQuality: number | null;
    imageQualityTaskId: number | null;
}

interface DispatchToProps {
    onChangeFrameStep(step: number): void;
    onChangeFrameSpeed(speed: FrameSpeed): void;
    onSwitchResetZoom(enabled: boolean): void;
    onSwitchRotateAll(rotateAll: boolean): void;
    onChangeCanvasBackgroundColor(color: string): void;
    onSwitchSmoothImage(enabled: boolean): void;
    onSwitchShowingDeletedFrames(enabled: boolean): void;
    onChangeImageQuality(taskId: number, imageQuality: number): Promise<void>;
}

function mapStateToProps(state: CombinedState): StateToProps {
    const {
        settings: { player },
        annotation: {
            job: { instance: jobInstance, meta },
        },
    } = state;

    const is2DJob = jobInstance?.dimension === DimensionType.DIMENSION_2D;

    return {
        ...player,
        imageQuality: is2DJob && typeof meta?.imageQuality === 'number' ? meta.imageQuality : null,
        imageQualityTaskId: is2DJob ? jobInstance?.taskId ?? null : null,
    };
}

function mapDispatchToProps(dispatch: any): DispatchToProps {
    return {
        onChangeFrameStep(step: number): void {
            dispatch(changeFrameStep(step));
        },
        onChangeFrameSpeed(speed: FrameSpeed): void {
            dispatch(changeFrameSpeed(speed));
        },
        onSwitchResetZoom(enabled: boolean): void {
            dispatch(switchResetZoom(enabled));
        },
        onSwitchRotateAll(rotateAll: boolean): void {
            dispatch(switchRotateAll(rotateAll));
        },
        onChangeCanvasBackgroundColor(color: string): void {
            dispatch(changeCanvasBackgroundColor(color));
        },
        onSwitchSmoothImage(enabled: boolean): void {
            dispatch(switchSmoothImage(enabled));
        },
        onSwitchShowingDeletedFrames(enabled: boolean): void {
            dispatch(switchShowingDeletedFrames(enabled));
        },
        async onChangeImageQuality(taskId: number, imageQuality: number): Promise<void> {
            const cvat = getCore();
            await cvat.server.request(`/api/tasks/${taskId}/data/meta`, {
                method: 'PATCH',
                data: { image_quality: imageQuality },
            });
        },
    };
}

export default connect(mapStateToProps, mapDispatchToProps)(PlayerSettingsComponent);
