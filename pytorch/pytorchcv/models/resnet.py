"""
    ResNet, implemented in PyTorch.
    Original paper: 'Deep Residual Learning for Image Recognition,' https://arxiv.org/abs/1512.03385.
"""

__all__ = ['ResNet', 'resnet10', 'resnet12', 'resnet14', 'resnet16', 'resnet18_wd4', 'resnet18_wd2', 'resnet18_w3d4',
           'resnet18', 'resnet34', 'resnet50', 'resnet50b', 'resnet101', 'resnet101b', 'resnet152', 'resnet152b',
           'resnet200', 'resnet200b', 'ResBlock', 'ResBottleneck', 'ResUnit', 'ResInitBlock']

import os
import torch.nn as nn
import torch.nn.init as init
from .common import conv1x1_block, conv3x3_block, conv7x7_block


class ResBlock(nn.Module):
    """
    Simple ResNet block for residual path in ResNet unit.

    Parameters:
    ----------
    in_channels : int
        Number of input channels.
    out_channels : int
        Number of output channels.
    stride : int or tuple/list of 2 int
        Strides of the convolution.
    """
    def __init__(self,
                 in_channels,
                 out_channels,
                 stride):
        super(ResBlock, self).__init__()
        self.conv1 = conv3x3_block(
            in_channels=in_channels,
            out_channels=out_channels,
            stride=stride)
        self.conv2 = conv3x3_block(
            in_channels=out_channels,
            out_channels=out_channels,
            activate=False)

    def forward(self, x):
        x = self.conv1(x)
        x = self.conv2(x)
        return x


class ResBottleneck(nn.Module):
    """
    ResNet bottleneck block for residual path in ResNet unit.

    Parameters:
    ----------
    in_channels : int
        Number of input channels.
    out_channels : int
        Number of output channels.
    stride : int or tuple/list of 2 int
        Strides of the convolution.
    conv1_stride : bool
        Whether to use stride in the first or the second convolution layer of the block.
    """
    def __init__(self,
                 in_channels,
                 out_channels,
                 stride,
                 conv1_stride):
        super(ResBottleneck, self).__init__()
        mid_channels = out_channels // 4

        self.conv1 = conv1x1_block(
            in_channels=in_channels,
            out_channels=mid_channels,
            stride=(stride if conv1_stride else 1))
        self.conv2 = conv3x3_block(
            in_channels=mid_channels,
            out_channels=mid_channels,
            stride=(1 if conv1_stride else stride))
        self.conv3 = conv1x1_block(
            in_channels=mid_channels,
            out_channels=out_channels,
            activate=False)

    def forward(self, x):
        x = self.conv1(x)
        x = self.conv2(x)
        x = self.conv3(x)
        return x


class ResUnit(nn.Module):
    """
    ResNet unit with residual connection.

    Parameters:
    ----------
    in_channels : int
        Number of input channels.
    out_channels : int
        Number of output channels.
    stride : int or tuple/list of 2 int
        Strides of the convolution.
    bottleneck : bool
        Whether to use a bottleneck or simple block in units.
    conv1_stride : bool
        Whether to use stride in the first or the second convolution layer of the block.
    """
    def __init__(self,
                 in_channels,
                 out_channels,
                 stride,
                 bottleneck,
                 conv1_stride):
        super(ResUnit, self).__init__()
        self.resize_identity = (in_channels != out_channels) or (stride != 1)

        if bottleneck:
            self.body = ResBottleneck(
                in_channels=in_channels,
                out_channels=out_channels,
                stride=stride,
                conv1_stride=conv1_stride)
        else:
            self.body = ResBlock(
                in_channels=in_channels,
                out_channels=out_channels,
                stride=stride)
        if self.resize_identity:
            self.identity_conv = conv1x1_block(
                in_channels=in_channels,
                out_channels=out_channels,
                stride=stride,
                activate=False)
        self.activ = nn.ReLU(inplace=True)

    def forward(self, x):
        if self.resize_identity:
            identity = self.identity_conv(x)
        else:
            identity = x
        x = self.body(x)
        x = x + identity
        x = self.activ(x)
        return x


class ResInitBlock(nn.Module):
    """
    ResNet specific initial block.

    Parameters:
    ----------
    in_channels : int
        Number of input channels.
    out_channels : int
        Number of output channels.
    """
    def __init__(self,
                 in_channels,
                 out_channels):
        super(ResInitBlock, self).__init__()
        self.conv = conv7x7_block(
            in_channels=in_channels,
            out_channels=out_channels,
            stride=2)
        self.pool = nn.MaxPool2d(
            kernel_size=3,
            stride=2,
            padding=1)

    def forward(self, x):
        x = self.conv(x)
        x = self.pool(x)
        return x


class ResNet(nn.Module):
    """
    ResNet model from 'Deep Residual Learning for Image Recognition,' https://arxiv.org/abs/1512.03385.

    Parameters:
    ----------
    channels : list of list of int
        Number of output channels for each unit.
    init_block_channels : int
        Number of output channels for the initial unit.
    bottleneck : bool
        Whether to use a bottleneck or simple block in units.
    conv1_stride : bool
        Whether to use stride in the first or the second convolution layer in units.
    in_channels : int, default 3
        Number of input channels.
    in_size : tuple of two ints, default (224, 224)
        Spatial size of the expected input image.
    num_classes : int, default 1000
        Number of classification classes.
    """
    def __init__(self,
                 channels,
                 init_block_channels,
                 bottleneck,
                 conv1_stride,
                 in_channels=3,
                 in_size=(224, 224),
                 num_classes=1000):
        super(ResNet, self).__init__()
        self.in_size = in_size
        self.num_classes = num_classes

        self.features = nn.Sequential()
        self.features.add_module("init_block", ResInitBlock(
            in_channels=in_channels,
            out_channels=init_block_channels))
        in_channels = init_block_channels
        for i, channels_per_stage in enumerate(channels):
            stage = nn.Sequential()
            for j, out_channels in enumerate(channels_per_stage):
                stride = 2 if (j == 0) and (i != 0) else 1
                stage.add_module("unit{}".format(j + 1), ResUnit(
                    in_channels=in_channels,
                    out_channels=out_channels,
                    stride=stride,
                    bottleneck=bottleneck,
                    conv1_stride=conv1_stride))
                in_channels = out_channels
            self.features.add_module("stage{}".format(i + 1), stage)
        self.features.add_module("final_pool", nn.AvgPool2d(
            kernel_size=7,
            stride=1))

        self.output = nn.Linear(
            in_features=in_channels,
            out_features=num_classes)

        self._init_params()

    def _init_params(self):
        for name, module in self.named_modules():
            if isinstance(module, nn.Conv2d):
                init.kaiming_uniform_(module.weight)
                if module.bias is not None:
                    init.constant_(module.bias, 0)

    def forward(self, x):
        x = self.features(x)
        x = x.view(x.size(0), -1)
        x = self.output(x)
        return x


def get_resnet(blocks,
               conv1_stride=True,
               width_scale=1.0,
               model_name=None,
               pretrained=False,
               root=os.path.join('~', '.torch', 'models'),
               **kwargs):
    """
    Create ResNet model with specific parameters.

    Parameters:
    ----------
    blocks : int
        Number of blocks.
    conv1_stride : bool
        Whether to use stride in the first or the second convolution layer in units.
    width_scale : float
        Scale factor for width of layers.
    model_name : str or None, default None
        Model name for loading pretrained model.
    pretrained : bool, default False
        Whether to load the pretrained weights for model.
    root : str, default '~/.torch/models'
        Location for keeping the model parameters.
    """

    if blocks == 10:
        layers = [1, 1, 1, 1]
    elif blocks == 12:
        layers = [2, 1, 1, 1]
    elif blocks == 14:
        layers = [2, 2, 1, 1]
    elif blocks == 16:
        layers = [2, 2, 2, 1]
    elif blocks == 18:
        layers = [2, 2, 2, 2]
    elif blocks == 34:
        layers = [3, 4, 6, 3]
    elif blocks == 50:
        layers = [3, 4, 6, 3]
    elif blocks == 101:
        layers = [3, 4, 23, 3]
    elif blocks == 152:
        layers = [3, 8, 36, 3]
    elif blocks == 200:
        layers = [3, 24, 36, 3]
    else:
        raise ValueError("Unsupported ResNet with number of blocks: {}".format(blocks))

    init_block_channels = 64

    if blocks < 50:
        channels_per_layers = [64, 128, 256, 512]
        bottleneck = False
    else:
        channels_per_layers = [256, 512, 1024, 2048]
        bottleneck = True

    channels = [[ci] * li for (ci, li) in zip(channels_per_layers, layers)]

    if width_scale != 1.0:
        channels = [[int(cij * width_scale) for cij in ci] for ci in channels]
        init_block_channels = int(init_block_channels * width_scale)

    net = ResNet(
        channels=channels,
        init_block_channels=init_block_channels,
        bottleneck=bottleneck,
        conv1_stride=conv1_stride,
        **kwargs)

    if pretrained:
        if (model_name is None) or (not model_name):
            raise ValueError("Parameter `model_name` should be properly initialized for loading pretrained model.")
        from .model_store import download_model
        download_model(
            net=net,
            model_name=model_name,
            local_model_store_dir_path=root)

    return net


def resnet10(**kwargs):
    """
    ResNet-10 model from 'Deep Residual Learning for Image Recognition,' https://arxiv.org/abs/1512.03385.
    It's an experimental model.

    Parameters:
    ----------
    pretrained : bool, default False
        Whether to load the pretrained weights for model.
    root : str, default '~/.torch/models'
        Location for keeping the model parameters.
    """
    return get_resnet(blocks=10, model_name="resnet10", **kwargs)


def resnet12(**kwargs):
    """
    ResNet-12 model from 'Deep Residual Learning for Image Recognition,' https://arxiv.org/abs/1512.03385.
    It's an experimental model.

    Parameters:
    ----------
    pretrained : bool, default False
        Whether to load the pretrained weights for model.
    root : str, default '~/.torch/models'
        Location for keeping the model parameters.
    """
    return get_resnet(blocks=12, model_name="resnet12", **kwargs)


def resnet14(**kwargs):
    """
    ResNet-14 model from 'Deep Residual Learning for Image Recognition,' https://arxiv.org/abs/1512.03385.
    It's an experimental model.

    Parameters:
    ----------
    pretrained : bool, default False
        Whether to load the pretrained weights for model.
    root : str, default '~/.torch/models'
        Location for keeping the model parameters.
    """
    return get_resnet(blocks=14, model_name="resnet14", **kwargs)


def resnet16(**kwargs):
    """
    ResNet-16 model from 'Deep Residual Learning for Image Recognition,' https://arxiv.org/abs/1512.03385.
    It's an experimental model.

    Parameters:
    ----------
    pretrained : bool, default False
        Whether to load the pretrained weights for model.
    root : str, default '~/.torch/models'
        Location for keeping the model parameters.
    """
    return get_resnet(blocks=16, model_name="resnet16", **kwargs)


def resnet18_wd4(**kwargs):
    """
    ResNet-18 model with 0.25 width scale from 'Deep Residual Learning for Image Recognition,'
    https://arxiv.org/abs/1512.03385. It's an experimental model.

    Parameters:
    ----------
    pretrained : bool, default False
        Whether to load the pretrained weights for model.
    root : str, default '~/.torch/models'
        Location for keeping the model parameters.
    """
    return get_resnet(blocks=18, width_scale=0.25, model_name="resnet18_wd4", **kwargs)


def resnet18_wd2(**kwargs):
    """
    ResNet-18 model with 0.5 width scale from 'Deep Residual Learning for Image Recognition,'
    https://arxiv.org/abs/1512.03385. It's an experimental model.

    Parameters:
    ----------
    pretrained : bool, default False
        Whether to load the pretrained weights for model.
    root : str, default '~/.torch/models'
        Location for keeping the model parameters.
    """
    return get_resnet(blocks=18, width_scale=0.5, model_name="resnet18_wd2", **kwargs)


def resnet18_w3d4(**kwargs):
    """
    ResNet-18 model with 0.75 width scale from 'Deep Residual Learning for Image Recognition,'
    https://arxiv.org/abs/1512.03385. It's an experimental model.

    Parameters:
    ----------
    pretrained : bool, default False
        Whether to load the pretrained weights for model.
    root : str, default '~/.torch/models'
        Location for keeping the model parameters.
    """
    return get_resnet(blocks=18, width_scale=0.75, model_name="resnet18_w3d4", **kwargs)


def resnet18(**kwargs):
    """
    ResNet-18 model from 'Deep Residual Learning for Image Recognition,' https://arxiv.org/abs/1512.03385.

    Parameters:
    ----------
    pretrained : bool, default False
        Whether to load the pretrained weights for model.
    root : str, default '~/.torch/models'
        Location for keeping the model parameters.
    """
    return get_resnet(blocks=18, model_name="resnet18", **kwargs)


def resnet34(**kwargs):
    """
    ResNet-34 model from 'Deep Residual Learning for Image Recognition,' https://arxiv.org/abs/1512.03385.

    Parameters:
    ----------
    pretrained : bool, default False
        Whether to load the pretrained weights for model.
    root : str, default '~/.torch/models'
        Location for keeping the model parameters.
    """
    return get_resnet(blocks=34, model_name="resnet34", **kwargs)


def resnet50(**kwargs):
    """
    ResNet-50 model from 'Deep Residual Learning for Image Recognition,' https://arxiv.org/abs/1512.03385.

    Parameters:
    ----------
    pretrained : bool, default False
        Whether to load the pretrained weights for model.
    root : str, default '~/.torch/models'
        Location for keeping the model parameters.
    """
    return get_resnet(blocks=50, model_name="resnet50", **kwargs)


def resnet50b(**kwargs):
    """
    ResNet-50 model with stride at the second convolution in bottleneck block from 'Deep Residual Learning for Image
    Recognition,' https://arxiv.org/abs/1512.03385.

    Parameters:
    ----------
    pretrained : bool, default False
        Whether to load the pretrained weights for model.
    root : str, default '~/.torch/models'
        Location for keeping the model parameters.
    """
    return get_resnet(blocks=50, conv1_stride=False, model_name="resnet50b", **kwargs)


def resnet101(**kwargs):
    """
    ResNet-101 model from 'Deep Residual Learning for Image Recognition,' https://arxiv.org/abs/1512.03385.

    Parameters:
    ----------
    pretrained : bool, default False
        Whether to load the pretrained weights for model.
    root : str, default '~/.torch/models'
        Location for keeping the model parameters.
    """
    return get_resnet(blocks=101, model_name="resnet101", **kwargs)


def resnet101b(**kwargs):
    """
    ResNet-101 model with stride at the second convolution in bottleneck block from 'Deep Residual Learning for Image
    Recognition,' https://arxiv.org/abs/1512.03385.

    Parameters:
    ----------
    pretrained : bool, default False
        Whether to load the pretrained weights for model.
    root : str, default '~/.torch/models'
        Location for keeping the model parameters.
    """
    return get_resnet(blocks=101, conv1_stride=False, model_name="resnet101b", **kwargs)


def resnet152(**kwargs):
    """
    ResNet-152 model from 'Deep Residual Learning for Image Recognition,' https://arxiv.org/abs/1512.03385.

    Parameters:
    ----------
    pretrained : bool, default False
        Whether to load the pretrained weights for model.
    root : str, default '~/.torch/models'
        Location for keeping the model parameters.
    """
    return get_resnet(blocks=152, model_name="resnet152", **kwargs)


def resnet152b(**kwargs):
    """
    ResNet-152 model with stride at the second convolution in bottleneck block from 'Deep Residual Learning for Image
    Recognition,' https://arxiv.org/abs/1512.03385.

    Parameters:
    ----------
    pretrained : bool, default False
        Whether to load the pretrained weights for model.
    root : str, default '~/.torch/models'
        Location for keeping the model parameters.
    """
    return get_resnet(blocks=152, conv1_stride=False, model_name="resnet152b", **kwargs)


def resnet200(**kwargs):
    """
    ResNet-200 model from 'Deep Residual Learning for Image Recognition,' https://arxiv.org/abs/1512.03385.
    It's an experimental model.

    Parameters:
    ----------
    pretrained : bool, default False
        Whether to load the pretrained weights for model.
    root : str, default '~/.torch/models'
        Location for keeping the model parameters.
    """
    return get_resnet(blocks=200, model_name="resnet200", **kwargs)


def resnet200b(**kwargs):
    """
    ResNet-200 model with stride at the second convolution in bottleneck block from 'Deep Residual Learning for Image
    Recognition,' https://arxiv.org/abs/1512.03385. It's an experimental model.

    Parameters:
    ----------
    pretrained : bool, default False
        Whether to load the pretrained weights for model.
    root : str, default '~/.torch/models'
        Location for keeping the model parameters.
    """
    return get_resnet(blocks=200, conv1_stride=False, model_name="resnet200b", **kwargs)


def _calc_width(net):
    import numpy as np
    net_params = filter(lambda p: p.requires_grad, net.parameters())
    weight_count = 0
    for param in net_params:
        weight_count += np.prod(param.size())
    return weight_count


def _test():
    import torch
    from torch.autograd import Variable

    pretrained = False

    models = [
        resnet10,
        resnet12,
        resnet14,
        resnet16,
        resnet18_wd4,
        resnet18_wd2,
        resnet18_w3d4,

        resnet18,
        resnet34,
        resnet50,
        resnet50b,
        resnet101,
        resnet101b,
        resnet152,
        resnet152b,
        resnet200,
        resnet200b,
    ]

    for model in models:

        net = model(pretrained=pretrained)

        # net.train()
        net.eval()
        weight_count = _calc_width(net)
        print("m={}, {}".format(model.__name__, weight_count))
        assert (model != resnet10 or weight_count == 5418792)
        assert (model != resnet12 or weight_count == 5492776)
        assert (model != resnet14 or weight_count == 5788200)
        assert (model != resnet16 or weight_count == 6968872)
        assert (model != resnet18_wd4 or weight_count == 831096)
        assert (model != resnet18_wd2 or weight_count == 3055880)
        assert (model != resnet18_w3d4 or weight_count == 6675352)
        assert (model != resnet18 or weight_count == 11689512)
        assert (model != resnet34 or weight_count == 21797672)
        assert (model != resnet50 or weight_count == 25557032)
        assert (model != resnet50b or weight_count == 25557032)
        assert (model != resnet101 or weight_count == 44549160)
        assert (model != resnet101b or weight_count == 44549160)
        assert (model != resnet152 or weight_count == 60192808)
        assert (model != resnet152b or weight_count == 60192808)
        assert (model != resnet200 or weight_count == 64673832)
        assert (model != resnet200b or weight_count == 64673832)

        x = Variable(torch.randn(1, 3, 224, 224))
        y = net(x)
        assert (tuple(y.size()) == (1, 1000))


if __name__ == "__main__":
    _test()
