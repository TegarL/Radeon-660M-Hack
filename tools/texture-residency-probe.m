// SPDX-License-Identifier: GPL-2.0-only
// Public standalone probe adapted from the local experiment on 2026-11-11.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static void expired(int signalNumber) { (void)signalNumber; _exit(124); }

static double uptime(void) {
    struct timespec value;
    clock_gettime(CLOCK_UPTIME_RAW, &value);
    return value.tv_sec + value.tv_nsec * 1e-9;
}

static void emit(NSDictionary *value) {
    NSData *data = [NSJSONSerialization dataWithJSONObject:value options:0 error:NULL];
    fwrite(data.bytes, 1, data.length, stdout);
    fputc('\n', stdout);
    fflush(stdout);
}

static BOOL completed(id<MTLCommandBuffer> commands, NSMutableDictionary *result) {
    [commands commit];
    [commands waitUntilCompleted];
    result[@"command_status"] = @(commands.status);
    if (commands.status != MTLCommandBufferStatusCompleted) {
        result[@"error"] = commands.error.localizedDescription ?: @"GPU command did not complete";
        emit(@{@"type": @"error", @"stage": @"command", @"details": result});
        return NO;
    }
    result[@"gpu_seconds"] = @(commands.GPUEndTime - commands.GPUStartTime);
    return YES;
}

static id<MTLComputePipelineState> fillPipeline;

static BOOL setupPattern(id<MTLDevice> device) {
    NSString *source = @"#include <metal_stdlib>\nusing namespace metal;\n"
        "kernel void fill(texture2d<half, access::write> image [[texture(0)]],"
        "constant uint &seed [[buffer(0)]], uint2 p [[thread_position_in_grid]]) {"
        "if (p.x >= image.get_width() || p.y >= image.get_height()) return;"
        "image.write(half4(half(p.x & 63u)/half(64), half(p.y & 63u)/half(64),"
        "half(seed+1u)/half(16), half(1)), p); }";
    NSError *error = nil;
    id<MTLLibrary> library = [device newLibraryWithSource:source options:nil error:&error];
    id<MTLFunction> function = [library newFunctionWithName:@"fill"];
    if (function) fillPipeline = [device newComputePipelineStateWithFunction:function error:&error];
    if (!fillPipeline) emit(@{@"type": @"error", @"stage": @"pattern_pipeline", @"error": error.localizedDescription ?: @"unavailable"});
    return fillPipeline != nil;
}

static BOOL readPattern(id<MTLDevice> device, id<MTLCommandQueue> queue, id<MTLTexture> texture,
                        unsigned seed, NSMutableDictionary *result) {
    NSUInteger stride = (texture.width * 8 + 255) & ~255ULL;
    id<MTLBuffer> buffer = [device newBufferWithLength:stride * texture.height options:MTLResourceStorageModeShared];
    if (!buffer) return NO;
    id<MTLCommandBuffer> commands = [queue commandBuffer];
    id<MTLBlitCommandEncoder> encoder = [commands blitCommandEncoder];
    [encoder copyFromTexture:texture sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0, 0, 0)
                 sourceSize:MTLSizeMake(texture.width, texture.height, 1) toBuffer:buffer destinationOffset:0
      destinationBytesPerRow:stride destinationBytesPerImage:stride * texture.height];
    [encoder endEncoding];
    if (!completed(commands, result)) return NO;
    for (unsigned yIndex = 0; yIndex < 4; yIndex++) for (unsigned xIndex = 0; xIndex < 4; xIndex++) {
        NSUInteger x = (texture.width - 1) * xIndex / 3, y = (texture.height - 1) * yIndex / 3;
        const uint16_t *pixel = (const uint16_t *)((const uint8_t *)buffer.contents + y * stride + x * 8);
        _Float16 expected[4] = {(_Float16)((x & 63) / 64.0f), (_Float16)((y & 63) / 64.0f),
                                (_Float16)((seed + 1) / 16.0f), (_Float16)1.0f};
        uint16_t bits[4];
        memcpy(bits, expected, sizeof(bits));
        if (memcmp(pixel, bits, sizeof(bits))) {
            emit(@{@"type": @"pixel_mismatch", @"seed": @(seed), @"x": @(x), @"y": @(y),
                   @"actual": @[@(pixel[0]), @(pixel[1]), @(pixel[2]), @(pixel[3])],
                   @"expected": @[@(bits[0]), @(bits[1]), @(bits[2]), @(bits[3])]});
            return NO;
        }
    }
    result[@"readback_pixels_checked"] = @16;
    return YES;
}

static id<MTLTexture> newLargeTexture(id<MTLDevice> device, id<MTLCommandQueue> queue, unsigned seed) {
    MTLTextureDescriptor *descriptor = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA16Float
        width:2182 height:1394 mipmapped:NO];
    descriptor.storageMode = MTLStorageModePrivate;
    descriptor.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
    descriptor.usage |= MTLTextureUsageShaderWrite;
    id<MTLTexture> texture = [device newTextureWithDescriptor:descriptor];
    if (!texture) return nil;
    id<MTLCommandBuffer> commands = [queue commandBuffer];
    id<MTLComputeCommandEncoder> encoder = [commands computeCommandEncoder];
    [encoder setComputePipelineState:fillPipeline];
    [encoder setTexture:texture atIndex:0];
    [encoder setBytes:&seed length:sizeof(seed) atIndex:0];
    [encoder dispatchThreads:MTLSizeMake(texture.width, texture.height, 1) threadsPerThreadgroup:MTLSizeMake(16, 16, 1)];
    [encoder endEncoding];
    NSMutableDictionary *result = [NSMutableDictionary new];
    return completed(commands, result) ? texture : nil;

}

static int workloads(id<MTLDevice> device) {
    id<MTLCommandQueue> queue = [device newCommandQueue];
    if (!queue) return 2;
    NSMutableArray<id<MTLTexture>> *textures = [NSMutableArray new];
    for (NSNumber *number in @[@1, @3, @6]) {
        unsigned stage = number.unsignedIntValue;
        double start = uptime();
        emit(@{@"type": @"residency_begin", @"phase": number});
        while (textures.count < stage) {
            id<MTLTexture> texture = newLargeTexture(device, queue, (unsigned)textures.count);
            if (!texture) return 3;
            [textures addObject:texture];
        }
        NSUInteger checked = 0;
        for (unsigned cycle = 0; cycle < 3; cycle++) {
            for (NSUInteger index = 0; index < textures.count; index++) {
                id<MTLTexture> texture = textures[index];
                @autoreleasepool {
                    NSMutableDictionary *result = [NSMutableDictionary new];
                    BOOL ok = readPattern(device, queue, texture, (unsigned)index, result);
                    if (!ok) return 4;
                    checked += [result[@"readback_pixels_checked"] unsignedIntegerValue];
                }
            }
        }
        emit(@{@"type": @"residency_complete", @"phase": number,
               @"elapsed_seconds": @(uptime() - start),
               @"texture_count": @(textures.count), @"texture_allocated_bytes": @(textures.count * textures[0].allocatedSize),
               @"readback_pixels_checked": @(checked), @"passed": @YES});
    }
    [textures removeAllObjects];
    return 0;
}

int main(int argc, const char **argv) {
    if (argc != 1 && !(argc == 2 && !strcmp(argv[1], "--pattern"))) {
        fputs("Usage: texture-residency-probe [--pattern]\n", stderr);
        return 64;
    }
    signal(SIGALRM, expired);
    alarm(20);
    @autoreleasepool {
        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        if (!device) return 6;
        if (!setupPattern(device)) return 7;
        emit(@{@"type": @"begin", @"device_name": device.name,
               @"scope": @"Retain one, three, then six private RGBA16Float textures; three pattern readback cycles per stage",
               @"texture_size": @[@2182, @1394], @"pattern_textures": @YES});
        int status;
        @autoreleasepool { status = workloads(device); }
        emit(@{@"type": @"complete", @"workload_exit_status": @(status), @"passed": status == 0 ? @YES : @NO});
        return status;
    }
}
